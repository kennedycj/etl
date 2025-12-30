"""Build general ledger from processed transaction files.

Creates a double-entry compatible ledger that can be exported to:
- Beancount
- Ledger CLI
- GnuCash
- CSV (for analysis)
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import csv
import pandas as pd

from finance_app.agents.data_curation.archive_scanner import get_archive_root
from finance_app.agents.ledger.transaction_classifier import (
    classify_transaction_type, create_ledger_postings, map_account_to_ledger_account
)


class LedgerEntry:
    """Represents a double-entry ledger transaction."""
    
    def __init__(self, date: datetime, description: str, postings: List[Tuple[str, Decimal]], 
                 metadata: Optional[Dict] = None):
        """Create a ledger entry.
        
        Args:
            date: Transaction date
            description: Transaction description
            postings: List of (account, amount) tuples - must sum to zero
            metadata: Optional metadata (transaction_id, source_file, etc.)
        """
        self.date = date
        self.description = description
        self.postings = postings  # [(account, amount), ...]
        self.metadata = metadata or {}
        
        # Validate double-entry: sum of amounts must be zero
        total = sum(amount for _, amount in postings)
        if abs(total) > Decimal('0.01'):  # Allow small rounding differences
            raise ValueError(f"Ledger entry does not balance: {total}")
    
    def __repr__(self):
        return f"LedgerEntry({self.date.strftime('%Y-%m-%d')}, {self.description}, {len(self.postings)} postings)"


class LedgerBuilder:
    """Build general ledger from processed transaction files."""
    
    def __init__(self, archive_root: Optional[Path] = None):
        """Initialize ledger builder.
        
        Args:
            archive_root: Archive root directory (uses default if None)
        """
        if archive_root is None:
            archive_root = get_archive_root()
        self.archive_root = Path(archive_root)
        self.processed_path = self.archive_root / "01_processed"
        self.ledger_path = self.archive_root / "20_ledger"
        
        # Ensure ledger directory exists
        self.ledger_path.mkdir(parents=True, exist_ok=True)
        
        self.entries: List[LedgerEntry] = []
        self.opening_balances: Dict[str, Decimal] = {}  # account -> balance
        self.adjustments: List[LedgerEntry] = []
    
    def load_processed_transactions(self) -> pd.DataFrame:
        """Load all processed transaction files into a single dataframe.
        
        Returns:
            DataFrame with all transactions from processed files
        """
        all_transactions = []
        
        if not self.processed_path.exists():
            return pd.DataFrame()
        
        # Find all CSV files (both cleansed_*.csv and regular *.csv)
        for csv_file in self.processed_path.rglob("*.csv"):
            try:
                df = pd.read_csv(csv_file)
                # Add source file metadata
                df['_source_file'] = str(csv_file.relative_to(self.processed_path))
                
                # Infer account name from file path if not present
                if 'Account Name' not in df.columns:
                    # Extract from path: bank/american_express/... -> American Express
                    path_parts = csv_file.relative_to(self.processed_path).parts
                    if len(path_parts) >= 2:
                        institution = path_parts[1].replace('_', ' ').title()
                        # Try to infer account type from filename or path
                        account_type = "Credit Card" if "american_express" in str(csv_file).lower() else "Account"
                        df['Account Name'] = f"{institution} - {account_type}"
                
                all_transactions.append(df)
            except Exception as e:
                print(f"Warning: Could not read {csv_file}: {e}")
                continue
        
        if not all_transactions:
            return pd.DataFrame()
        
        # Combine all dataframes
        combined = pd.concat(all_transactions, ignore_index=True)
        return combined
    
    def convert_transaction_to_ledger_entry(self, row: pd.Series, account_mapping: Dict[str, str]) -> Optional[LedgerEntry]:
        """Convert a transaction row to a ledger entry.
        
        Args:
            row: Transaction row from processed CSV
            account_mapping: Maps account names/IDs to ledger account names
            
        Returns:
            LedgerEntry or None if conversion fails
        """
        # Extract key fields (adjust based on your CSV structure)
        try:
            # Try to find date column
            date_col = None
            for col in ['_parsed_date', 'Date', 'date', 'Transaction Date']:
                if col in row.index and pd.notna(row[col]):
                    date_col = col
                    break
            
            if not date_col:
                return None
            
            # Parse date
            date_val = row[date_col]
            if isinstance(date_val, str):
                # Try different date formats
                try:
                    date = datetime.strptime(date_val, '%Y-%m-%d')
                except ValueError:
                    try:
                        date = datetime.strptime(date_val, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        date = pd.to_datetime(date_val).to_pydatetime()
            else:
                date = pd.to_datetime(date_val).to_pydatetime()
            
            # Get amount
            amount_col = None
            for col in ['_parsed_amount', 'Amount', 'amount']:
                if col in row.index and pd.notna(row[col]):
                    amount_col = col
                    break
            
            if not amount_col:
                return None
            
            amount = Decimal(str(row[amount_col]))
            
            # Get account
            account_name = None
            for col in ['Account Name', 'account_name', 'Account']:
                if col in row.index and pd.notna(row[col]):
                    account_name = str(row[col])
                    break
            
            if not account_name:
                return None
            
            # Map to ledger account
            ledger_account = account_mapping.get(account_name, account_name)
            
            # Get description (try multiple columns)
            description = ""
            for col in ['Original Description', 'Description', 'Simple Description', 'description', 'Memo', 'memo']:
                if col in row.index and pd.notna(row[col]):
                    desc_val = str(row[col]).strip()
                    if desc_val:
                        description = desc_val
                        break
            
            if not description:
                description = "Transaction"
            
            # Get category if available
            category = None
            for col in ['Category', 'category', 'Classification', 'classification']:
                if col in row.index and pd.notna(row[col]):
                    category = str(row[col]).strip()
                    break
            
            # Get original description (contains transfer source info)
            original_description = None
            for col in ['Original Description', 'original_description']:
                if col in row.index and pd.notna(row[col]):
                    original_description = str(row[col]).strip()
                    break
            
            # Determine account type from account name or file path
            account_type = self._infer_account_type(account_name, row.get('_source_file', ''))
            
            # Extract institution
            institution = self._extract_institution(account_name, row.get('_source_file', ''))
            
            # Classify transaction type
            tx_type = classify_transaction_type(description, amount, account_type, category, original_description)
            
            # Check if it's a transfer and extract source/target accounts
            source_account_name = None
            target_account_name = None
            if tx_type == 'transfer':
                from finance_app.agents.ledger.transaction_classifier import extract_transfer_accounts, map_account_identifier_to_name
                transfer_info = extract_transfer_accounts(original_description or description, account_name, category)
                if transfer_info:
                    source_desc, target_desc = transfer_info
                    # Determine which is the identifier vs full account name
                    # If source_desc looks like an identifier (e.g., "chk 0129"), map it
                    if len(source_desc.split()) <= 3 and any(x in source_desc.lower() for x in ['chk', 'sav', 'cd']):
                        source_account_name = self._map_transfer_source_to_account(source_desc, institution)
                        # target_desc should be the full account name
                        target_account_name = target_desc
                    else:
                        # source_desc is the full account name, target_desc is the identifier
                        source_account_name = source_desc
                        # Map target identifier to account name
                        if len(target_desc.split()) <= 3 and any(x in target_desc.lower() for x in ['chk', 'sav', 'cd']):
                            target_account_name = map_account_identifier_to_name(target_desc, institution) or target_desc
                        else:
                            target_account_name = target_desc
            
            # Create double-entry postings (pass account names, not ledger accounts - postings function handles mapping)
            postings = create_ledger_postings(
                account_name, amount, tx_type, description,
                other_account=None, category=category,
                source_account_name=source_account_name,
                target_account_name=target_account_name,
                institution=institution
            )
            
            metadata = {
                'source_file': row.get('_source_file', ''),
                'account_name': account_name,
                'category': category,
                'transaction_type': tx_type
            }
            
            # Create ledger entry
            entry = LedgerEntry(date, description, postings, metadata)
            return entry
            
        except Exception as e:
            return None
    
    def create_account_mapping(self) -> Dict[str, str]:
        """Create mapping from account names to ledger account names.
        
        Returns:
            Dictionary mapping account names to ledger account hierarchy
        """
        # This is now handled dynamically in convert_transaction_to_ledger_entry
        # using map_account_to_ledger_account function
        return {}
    
    def _infer_account_type(self, account_name: str, source_file: str) -> str:
        """Infer account type from account name or file path.
        
        Args:
            account_name: Account name from CSV
            source_file: Source file path
            
        Returns:
            Account type string (checking, savings, credit_card, etc.)
        """
        account_lower = account_name.lower()
        file_lower = source_file.lower()
        
        # Check account name first
        if 'credit card' in account_lower or 'american express' in account_lower:
            return 'credit_card'
        elif 'checking' in account_lower or 'bank' in account_lower:
            return 'checking'
        elif 'savings' in account_lower:
            return 'savings'
        elif 'cd' in account_lower:
            return 'cd'
        elif 'mortgage' in account_lower:
            return 'mortgage'
        elif 'heloc' in account_lower:
            return 'heloc'
        
        # Fallback to file path
        if 'american_express' in file_lower:
            return 'credit_card'
        elif 'checking' in file_lower or 'bank' in file_lower:
            return 'checking'
        elif 'savings' in file_lower:
            return 'savings'
        
        # Default
        return 'checking'
    
    def _extract_institution(self, account_name: str, source_file: str) -> str:
        """Extract institution name from account name or file path.
        
        Args:
            account_name: Account name from CSV
            source_file: Source file path
            
        Returns:
            Institution name
        """
        # Try account name first
        if 'Bank of America' in account_name:
            return 'BankOfAmerica'
        elif 'American Express' in account_name:
            return 'AmericanExpress'
        elif 'Chase' in account_name:
            return 'Chase'
        
        # Fallback to file path
        file_lower = source_file.lower()
        if 'bank_of_america' in file_lower or 'boa' in file_lower:
            return 'BankOfAmerica'
        elif 'american_express' in file_lower:
            return 'AmericanExpress'
        elif 'chase' in file_lower:
            return 'Chase'
        
        # Default
        return 'Unknown'
    
    def _map_transfer_source_to_account(self, source_description: str, institution: str) -> str:
        """Map transfer source description to account name.
        
        Args:
            source_description: Source account description (e.g., "CHK 0129")
            institution: Institution name
            
        Returns:
            Mapped account name
        """
        from finance_app.agents.ledger.transaction_classifier import map_account_identifier_to_name
        
        mapped = map_account_identifier_to_name(source_description, institution)
        if mapped:
            return mapped
        
        # Fallback: try to construct from description
        desc_lower = source_description.lower()
        if 'chk' in desc_lower or 'checking' in desc_lower:
            return f"{institution} - Bank - Checking"
        elif 'sav' in desc_lower or 'savings' in desc_lower:
            return f"{institution} - Bank - Savings"
        else:
            # Default to checking
            return f"{institution} - Bank - Checking"
    
    def build_ledger_from_processed_files(self):
        """Build ledger from all processed transaction files."""
        transactions_df = self.load_processed_transactions()
        
        if transactions_df.empty:
            print("No processed transactions found")
            return
        
        print(f"Loaded {len(transactions_df)} transactions from processed files")
        
        account_mapping = self.create_account_mapping()
        
        # Convert transactions to ledger entries
        converted = 0
        failed = 0
        errors = []
        for idx, row in transactions_df.iterrows():
            try:
                entry = self.convert_transaction_to_ledger_entry(row, account_mapping)
                if entry:
                    self.entries.append(entry)
                    converted += 1
                else:
                    failed += 1
                    if failed <= 3:
                        errors.append(f"Row {idx}: Entry was None")
            except Exception as e:
                failed += 1
                if len(errors) < 5:  # Collect first 5 errors
                    import traceback
                    errors.append(f"Row {idx}: {str(e)}")
        
        if errors:
            print("\nFirst few conversion errors:")
            for err in errors[:5]:
                print(f"  {err}")
        
        print(f"Converted {converted} transactions to ledger entries")
        if failed > 0:
            print(f"Failed to convert {failed} transactions")
        
        # Sort entries by date
        self.entries.sort(key=lambda e: e.date)
    
    def export_to_beancount(self, output_path: Optional[Path] = None) -> str:
        """Export ledger to Beancount format.
        
        Args:
            output_path: Path to write Beancount file (default: ledger_path/ledger.beancount)
            
        Returns:
            Beancount format string
        """
        if output_path is None:
            output_path = self.ledger_path / "ledger.beancount"
        
        lines = []
        lines.append("; Beancount ledger generated from processed transactions")
        lines.append(f"; Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Opening balances
        for account, balance in self.opening_balances.items():
            if balance != 0:
                date_str = self.entries[0].date.strftime('%Y-%m-%d') if self.entries else datetime.now().strftime('%Y-%m-%d')
                lines.append(f"{date_str} open {account}")
                lines.append(f"{date_str} balance {account} {balance:,.2f} USD")
        
        lines.append("")
        
        # Transactions
        for entry in self.entries:
            date_str = entry.date.strftime('%Y-%m-%d')
            lines.append(f"{date_str} * \"{entry.description}\"")
            
            for account, amount in entry.postings:
                lines.append(f"  {account}  {amount:,.2f} USD")
            
            if entry.metadata:
                for key, value in entry.metadata.items():
                    lines.append(f"  ; {key}: {value}")
            lines.append("")
        
        content = "\n".join(lines)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return content
    
    def export_to_ledger_cli(self, output_path: Optional[Path] = None) -> str:
        """Export ledger to Ledger CLI format.
        
        Args:
            output_path: Path to write Ledger file (default: ledger_path/ledger.dat)
            
        Returns:
            Ledger CLI format string
        """
        if output_path is None:
            output_path = self.ledger_path / "ledger.dat"
        
        lines = []
        lines.append("; Ledger CLI format ledger generated from processed transactions")
        lines.append(f"; Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Transactions
        for entry in self.entries:
            date_str = entry.date.strftime('%Y/%m/%d')
            lines.append(f"{date_str} {entry.description}")
            
            for account, amount in entry.postings:
                lines.append(f"    {account}  ${amount:,.2f}")
            
            lines.append("")
        
        content = "\n".join(lines)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return content
    
    def export_to_csv(self, output_path: Optional[Path] = None):
        """Export ledger entries to CSV format.
        
        Args:
            output_path: Path to write CSV file (default: ledger_path/ledger.csv)
        """
        if output_path is None:
            output_path = self.ledger_path / "ledger.csv"
        
        rows = []
        for entry in self.entries:
            for account, amount in entry.postings:
                rows.append({
                    'date': entry.date.strftime('%Y-%m-%d'),
                    'description': entry.description,
                    'account': account,
                    'amount': float(amount),
                    'source_file': entry.metadata.get('source_file', ''),
                    'transaction_id': entry.metadata.get('transaction_id', '')
                })
        
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)
    
    def save_opening_balances(self, output_path: Optional[Path] = None):
        """Save opening balances to CSV.
        
        Args:
            output_path: Path to write CSV (default: ledger_path/opening_balances.csv)
        """
        if output_path is None:
            output_path = self.ledger_path / "opening_balances.csv"
        
        rows = []
        for account, balance in self.opening_balances.items():
            rows.append({
                'account': account,
                'balance': float(balance),
                'currency': 'USD'
            })
        
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)
    
    def save_adjustments(self, output_path: Optional[Path] = None):
        """Save adjustments/reconciliations to CSV.
        
        Args:
            output_path: Path to write CSV (default: ledger_path/adjustments.csv)
        """
        if output_path is None:
            output_path = self.ledger_path / "adjustments.csv"
        
        rows = []
        for entry in self.adjustments:
            for account, amount in entry.postings:
                rows.append({
                    'date': entry.date.strftime('%Y-%m-%d'),
                    'description': entry.description,
                    'account': account,
                    'amount': float(amount),
                    'reason': entry.metadata.get('reason', '')
                })
        
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)

