"""TSV file importer for transaction statements."""

import csv
import re
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple
from uuid import uuid4

from sqlalchemy.orm import Session

from finance_app.database.models import AccountModel, TransactionModel
from finance_app.models.account import AccountType


def parse_account_type_from_name(account_name: str) -> AccountType:
    """Infer account type from account name.
    
    Examples:
        "Bank of America - Credit Card - ..." -> CREDIT_CARD
        "Bank of America - Bank - 7M FEATURED CD" -> CD
        "Bank of America - Bank - ..." -> CHECKING (default)
    """
    account_name_lower = account_name.lower()
    
    if "credit card" in account_name_lower or "visa" in account_name_lower or "mastercard" in account_name_lower:
        return AccountType.CREDIT_CARD
    elif "cd" in account_name_lower:
        return AccountType.CD
    elif "savings" in account_name_lower:
        return AccountType.SAVINGS
    elif "checking" in account_name_lower or "bank" in account_name_lower:
        return AccountType.CHECKING
    elif "mortgage" in account_name_lower:
        return AccountType.MORTGAGE
    elif "heloc" in account_name_lower:
        return AccountType.HELOC
    elif "401" in account_name_lower or "401k" in account_name_lower:
        return AccountType.K401
    elif "ira" in account_name_lower:
        if "roth" in account_name_lower:
            return AccountType.IRA_ROTH
        elif "rollover" in account_name_lower:
            return AccountType.IRA_ROLLOVER
        else:
            return AccountType.IRA_TRADITIONAL
    elif "529" in account_name_lower:
        return AccountType.K529
    elif "able" in account_name_lower:
        return AccountType.ABLE
    elif "brokerage" in account_name_lower or "investment" in account_name_lower:
        return AccountType.BROKERAGE
    else:
        return AccountType.CHECKING  # Default


def parse_institution_from_name(account_name: str) -> str:
    """Extract institution name from account name.
    
    Example: "Bank of America - Credit Card - ..." -> "Bank of America"
    """
    if " - " in account_name:
        return account_name.split(" - ")[0]
    return account_name.split(" ")[0] if account_name else "Unknown"


def get_or_create_account(session: Session, account_name: str, institution_name: Optional[str] = None) -> Tuple[AccountModel, bool]:
    """Get existing account by name or create a new one.
    
    Returns:
        Tuple of (AccountModel, created) where created is True if account was just created
    """
    
    # Try to find existing account
    account = session.query(AccountModel).filter(AccountModel.name == account_name).first()
    
    if account:
        return account, False
    
    # Create new account
    if institution_name is None:
        institution_name = parse_institution_from_name(account_name)
    
    account_type = parse_account_type_from_name(account_name)
    
    account = AccountModel(
        id=uuid4(),
        name=account_name,
        account_type=account_type.value,
        institution_name=institution_name,
        currency="USD",
        open_date=datetime.utcnow()
    )
    
    session.add(account)
    session.flush()  # Get the ID without committing
    return account, True


def parse_date(date_str: str) -> datetime:
    """Parse date string in various formats."""
    date_str = date_str.strip()
    
    # Try common formats
    formats = ["%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%Y/%m/%d"]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # If all fail, try dateutil parser
    from dateutil import parser
    return parser.parse(date_str)


def clean_amount(amount_str: str) -> Decimal:
    """Clean and parse amount string (handles commas, negative signs)."""
    # Remove commas and whitespace
    amount_str = amount_str.replace(",", "").strip()
    return Decimal(amount_str)


def detect_delimiter(file_path: str) -> str:
    """Detect delimiter (comma or tab) from file extension and content."""
    # Check extension first
    if file_path.lower().endswith('.csv'):
        return ','
    elif file_path.lower().endswith('.tsv'):
        return '\t'
    
    # Auto-detect by reading first line
    with open(file_path, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        # Count commas and tabs
        comma_count = first_line.count(',')
        tab_count = first_line.count('\t')
        return ',' if comma_count > tab_count else '\t'


def import_tsv(session: Session, tsv_file_path: str) -> Tuple[int, int]:
    """Import transactions from TSV or CSV file.
    
    Returns:
        Tuple of (accounts_created, transactions_imported)
    """
    accounts_created = 0
    transactions_imported = 0
    
    delimiter = detect_delimiter(tsv_file_path)
    
    with open(tsv_file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 because row 1 is header
            try:
                # Skip empty rows
                if not row.get('Date') or not row.get('Amount'):
                    continue
                
                # Get or create account
                account_name = row.get('Account Name', '').strip()
                if not account_name:
                    print(f"Warning: Row {row_num} missing Account Name, skipping")
                    continue
                
                account, created = get_or_create_account(session, account_name)
                if created:
                    accounts_created += 1
                
                # Parse transaction date
                transaction_date = parse_date(row['Date'])
                
                # Parse amount
                amount = clean_amount(row['Amount'])
                
                # Map status
                status = row.get('Status', 'posted').strip().lower()
                
                # Create transaction
                transaction = TransactionModel(
                    id=uuid4(),
                    account_id=account.id,
                    transaction_date=transaction_date,
                    amount=amount,
                    currency=row.get('Currency', 'USD').strip(),
                    description=row.get('Original Description', '').strip(),
                    simple_description=row.get('Simple Description', '').strip() or None,
                    category=row.get('Category', '').strip() or None,
                    classification=row.get('Classification', '').strip() or None,
                    status=status,
                    memo=row.get('Memo', '').strip() or None,
                    user_description=row.get('User Description', '').strip() or None,
                    is_external=True,
                    reconcile_status='unreconciled' if status == 'pending' else 'cleared'
                )
                
                session.add(transaction)
                transactions_imported += 1
                
            except Exception as e:
                print(f"Error importing row {row_num}: {e}")
                print(f"Row data: {row}")
                continue
    
    session.commit()
    return accounts_created, transactions_imported


if __name__ == "__main__":
    import sys
    from finance_app.database.connection import create_database_engine, get_session
    
    if len(sys.argv) < 3:
        print("Usage: python -m finance_app.importers.tsv_importer <database_url> <tsv_file>")
        print("Example: python -m finance_app.importers.tsv_importer postgresql://user:pass@localhost/finance transactions.tsv")
        sys.exit(1)
    
    database_url = sys.argv[1]
    tsv_file = sys.argv[2]
    
    engine = create_database_engine(database_url)
    session = get_session(engine)
    
    try:
        accounts_created, transactions_imported = import_tsv(session, tsv_file)
        print(f"✓ Imported {transactions_imported} transactions")
        print(f"✓ Created {accounts_created} new accounts")
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
        raise
    finally:
        session.close()

