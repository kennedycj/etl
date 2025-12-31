"""Match transactions across accounts to create proper double-entry postings.

This module identifies and matches related transactions (e.g., credit card payments)
that appear in multiple accounts and creates corrected ledger entries.
"""

from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass
import pandas as pd
from pathlib import Path


@dataclass
class TransactionMatch:
    """Represents a matched pair of transactions."""
    checking_entry: Dict
    credit_card_entry: Dict
    amount: Decimal
    date: datetime
    confidence: float
    match_reasons: List[str]


class AccountMatcher:
    """Match transactions across accounts for proper double-entry accounting."""
    
    def __init__(self, ledger_path: Path, max_date_diff_days: int = 3):
        """Initialize account matcher.
        
        Args:
            ledger_path: Path to ledger CSV file
            max_date_diff_days: Maximum days difference for matching (default 3)
        """
        self.ledger_path = ledger_path
        self.max_date_diff_days = max_date_diff_days
        self.ledger_df: Optional[pd.DataFrame] = None
        self.matches: List[TransactionMatch] = []
    
    def load_ledger(self) -> pd.DataFrame:
        """Load ledger CSV file."""
        if self.ledger_df is not None:
            return self.ledger_df
        
        self.ledger_df = pd.read_csv(self.ledger_path)
        self.ledger_df['date'] = pd.to_datetime(self.ledger_df['date'])
        self.ledger_df['amount'] = pd.to_numeric(self.ledger_df['amount'], errors='coerce')
        
        return self.ledger_df
    
    def find_credit_card_payments(self) -> List[TransactionMatch]:
        """Find and match credit card payment transactions.
        
        Returns:
            List of matched transaction pairs
        """
        df = self.load_ledger()
        matches = []
        
        # Find credit card payment transactions from checking accounts
        # These show up as: Assets:Checking -> Liabilities:CreditCards:BankOfAmerica
        # But the credit card might be wrong (should match the actual card)
        checking_payments = df[
            (df['account'].str.startswith('Assets:', na=False)) &
            (df['amount'] < 0) &  # Negative = money leaving checking
            (df['description'].str.contains('AMERICAN EXPRESS|ACH PMT|PAYMENT', case=False, na=False))
        ].copy()
        
        # Find corresponding credit card transactions
        # These show up as: Liabilities:CreditCards:XXX -> Expenses:Uncategorized
        credit_card_payments = df[
            (df['account'].str.startswith('Liabilities:CreditCards:', na=False)) &
            (df['amount'] < 0) &  # Negative = reducing liability
            (df['description'].str.contains('ONLINE PAYMENT|PAYMENT - THANK YOU', case=False, na=False))
        ].copy()
        
        # Try to match them
        for _, checking_row in checking_payments.iterrows():
            checking_date = checking_row['date']
            checking_amount = abs(checking_row['amount'])  # Use absolute value for matching
            checking_desc = str(checking_row['description']).lower()
            checking_source = str(checking_row.get('_source_file', ''))
            
            # Extract credit card name from description if possible
            # "AMERICAN EXPRESS DES:ACH PMT" -> "AmericanExpress"
            card_name = None
            if 'american express' in checking_desc:
                card_name = 'AmericanExpress'
            elif 'bank of america' in checking_desc and 'credit' in checking_desc:
                card_name = 'BankOfAmerica'
            
            # Find matching credit card transaction
            for _, cc_row in credit_card_payments.iterrows():
                cc_date = cc_row['date']
                cc_amount = abs(cc_row['amount'])
                cc_desc = str(cc_row['description']).lower()
                cc_source = str(cc_row.get('_source_file', ''))
                cc_account = str(cc_row['account'])
                
                # Extract card name from account
                # "Liabilities:CreditCards:AmericanExpress" -> "AmericanExpress"
                cc_account_card = None
                if 'Liabilities:CreditCards:' in cc_account:
                    cc_account_card = cc_account.split('Liabilities:CreditCards:')[-1]
                
                # Match criteria
                match_reasons = []
                confidence = 0.0
                
                # 1. Amount match (exact or very close - within 0.01)
                amount_diff = abs(checking_amount - cc_amount)
                if amount_diff < 0.01:
                    match_reasons.append(f"Amount match: ${checking_amount:.2f}")
                    confidence += 0.4
                elif amount_diff < 1.0:
                    match_reasons.append(f"Amount close: ${checking_amount:.2f} vs ${cc_amount:.2f} (diff: ${amount_diff:.2f})")
                    confidence += 0.2
                else:
                    continue  # Amounts too different
                
                # 2. Date match (within max_date_diff_days)
                date_diff = abs((checking_date - cc_date).days)
                if date_diff == 0:
                    match_reasons.append("Same date")
                    confidence += 0.3
                elif date_diff <= self.max_date_diff_days:
                    match_reasons.append(f"Date within {date_diff} days")
                    confidence += 0.2
                else:
                    continue  # Dates too far apart
                
                # 3. Card name match
                if card_name and cc_account_card and card_name == cc_account_card:
                    match_reasons.append(f"Card name match: {card_name}")
                    confidence += 0.2
                elif card_name or cc_account_card:
                    # Partial match - one side identified the card
                    match_reasons.append(f"Partial card match: {card_name or cc_account_card}")
                    confidence += 0.1
                
                # 4. Source file match (both from bank accounts)
                if 'bank' in checking_source.lower() and 'bank' in cc_source.lower():
                    match_reasons.append("Both from bank sources")
                    confidence += 0.1
                
                # 5. Description pattern match
                # "AMERICAN EXPRESS DES:ACH PMT" should match "ONLINE PAYMENT - THANK YOU"
                # Both are payment-related
                if 'payment' in checking_desc and 'payment' in cc_desc:
                    match_reasons.append("Both payment descriptions")
                    confidence += 0.1
                
                # If confidence is high enough, create a match
                if confidence >= 0.6:  # Minimum threshold
                    match = TransactionMatch(
                        checking_entry=checking_row.to_dict(),
                        credit_card_entry=cc_row.to_dict(),
                        amount=checking_amount,
                        date=checking_date,
                        confidence=confidence,
                        match_reasons=match_reasons
                    )
                    matches.append(match)
                    break  # Found a match, move to next checking payment
        
        self.matches = matches
        return matches
    
    def create_corrected_entries(self) -> pd.DataFrame:
        """Create corrected ledger entries for matched transactions.
        
        Returns:
            DataFrame with corrected entries
        """
        if not self.matches:
            return pd.DataFrame()
        
        corrected_entries = []
        
        for match in self.matches:
            checking_entry = match.checking_entry
            cc_entry = match.credit_card_entry
            
            # Extract the correct credit card from the credit card entry
            cc_account = str(cc_entry['account'])
            if 'Liabilities:CreditCards:' in cc_account:
                correct_cc = cc_account.split('Liabilities:CreditCards:')[-1]
            else:
                continue
            
            # Get original description (prefer checking entry as it's more descriptive)
            orig_desc = str(checking_entry.get('description', ''))
            if not orig_desc or len(orig_desc) < 10:
                orig_desc = str(cc_entry.get('description', ''))
            
            # Get source file (prefer checking entry)
            source_file = checking_entry.get('_source_file', '') or cc_entry.get('_source_file', '')
            
            # Create corrected entry: Assets:Checking -> Liabilities:CreditCards:CorrectCard
            # Entry 1: Checking (negative)
            corrected_entries.append({
                'date': match.date,
                'description': orig_desc,
                'account': checking_entry['account'],
                'amount': -match.amount,
                '_source_file': source_file,
                '_original_entry': 'checking_payment',
                '_match_confidence': match.confidence,
                '_match_reasons': '; '.join(match.match_reasons)
            })
            
            # Entry 2: Credit card liability (positive - reduces liability)
            corrected_entries.append({
                'date': match.date,
                'description': orig_desc,
                'account': f"Liabilities:CreditCards:{correct_cc}",
                'amount': match.amount,
                '_source_file': source_file,
                '_original_entry': 'credit_card_payment',
                '_match_confidence': match.confidence,
                '_match_reasons': '; '.join(match.match_reasons)
            })
        
        return pd.DataFrame(corrected_entries)
    
    def create_reconciled_ledger(self, output_path: Optional[Path] = None) -> pd.DataFrame:
        """Create a reconciled ledger with corrected entries replacing incorrect ones.
        
        Args:
            output_path: Optional path to save reconciled ledger
            
        Returns:
            DataFrame with reconciled ledger entries
        """
        df = self.load_ledger()
        
        if not self.matches:
            return df
        
        # Get indices of entries to remove (the matched incorrect entries)
        indices_to_remove = set()
        
        for match in self.matches:
            checking_entry = match.checking_entry
            cc_entry = match.credit_card_entry
            
            # Extract the correct credit card from the credit card entry
            cc_account = str(cc_entry['account'])
            if 'Liabilities:CreditCards:' in cc_account:
                correct_cc = cc_account.split('Liabilities:CreditCards:')[-1]
            else:
                continue
            
            # Find and mark the incorrect entries for removal
            # 1. The checking -> wrong credit card entry
            # This is the entry where checking goes to the WRONG credit card (BankOfAmerica instead of AmericanExpress)
            checking_mask = (
                (df['date'] == match.date) &
                (df['account'] == checking_entry['account']) &
                (df['amount'] == checking_entry['amount'])
            )
            # Further filter: should be going to a credit card liability that's NOT the correct one
            checking_indices = df[checking_mask].index
            for idx in checking_indices:
                # Check if there's a corresponding credit card entry on the same date with wrong card
                same_date_mask = (
                    (df['date'] == match.date) &
                    (df['account'].str.startswith('Liabilities:CreditCards:', na=False)) &
                    (df['amount'] == abs(match.amount))
                )
                wrong_card_indices = df[same_date_mask].index
                for wrong_idx in wrong_card_indices:
                    wrong_card = str(df.loc[wrong_idx, 'account']).split('Liabilities:CreditCards:')[-1]
                    if wrong_card != correct_cc:
                        # This is the wrong entry - mark both for removal
                        indices_to_remove.add(idx)
                        indices_to_remove.add(wrong_idx)
            
            # 2. The credit card -> expense entry (the uninformative one)
            # Find the credit card entry that goes to Expenses:Uncategorized
            cc_mask = (
                (df['date'] == match.date) &
                (df['account'] == cc_entry['account']) &
                (df['amount'] == cc_entry['amount'])
            )
            cc_indices = df[cc_mask].index
            for idx in cc_indices:
                # Check if there's a corresponding expense entry
                expense_mask = (
                    (df['date'] == match.date) &
                    (df['account'].str.startswith('Expenses:', na=False)) &
                    (df['amount'] == abs(match.amount))
                )
                expense_indices = df[expense_mask].index
                for exp_idx in expense_indices:
                    # If the expense entry is on the same date and amount, it's likely the pair
                    indices_to_remove.add(idx)
                    indices_to_remove.add(exp_idx)
        
        # Remove incorrect entries
        reconciled_df = df.drop(indices_to_remove).copy()
        
        # Add corrected entries
        corrected_df = self.create_corrected_entries()
        if len(corrected_df) > 0:
            # Convert corrected entries to match ledger format
            corrected_df['date'] = pd.to_datetime(corrected_df['date'])
            # Rename columns to match ledger format
            if 'source_file' not in corrected_df.columns and '_source_file' in corrected_df.columns:
                corrected_df['source_file'] = corrected_df['_source_file']
            
            # Append corrected entries
            reconciled_df = pd.concat([reconciled_df, corrected_df], ignore_index=True)
            reconciled_df = reconciled_df.sort_values('date')
        
        # Save if output path provided
        if output_path:
            reconciled_df.to_csv(output_path, index=False)
        
        return reconciled_df
    
    def generate_reconciliation_report(self) -> str:
        """Generate a report of matched transactions."""
        if not self.matches:
            return "No matches found."
        
        report = []
        report.append("="*80)
        report.append("CREDIT CARD PAYMENT MATCHING REPORT")
        report.append("="*80)
        report.append(f"\nFound {len(self.matches)} matched transaction pairs\n")
        
        for i, match in enumerate(self.matches, 1):
            report.append(f"\nMatch #{i} (Confidence: {match.confidence:.1%})")
            report.append("-" * 80)
            report.append(f"Date: {match.date.strftime('%Y-%m-%d')}")
            report.append(f"Amount: ${match.amount:,.2f}")
            report.append(f"\nChecking Entry:")
            report.append(f"  Account: {match.checking_entry['account']}")
            report.append(f"  Description: {match.checking_entry['description'][:60]}")
            report.append(f"  Source: {match.checking_entry.get('_source_file', 'N/A')}")
            report.append(f"\nCredit Card Entry:")
            report.append(f"  Account: {match.credit_card_entry['account']}")
            report.append(f"  Description: {match.credit_card_entry['description'][:60]}")
            report.append(f"  Source: {match.credit_card_entry.get('_source_file', 'N/A')}")
            report.append(f"\nMatch Reasons:")
            for reason in match.match_reasons:
                report.append(f"  - {reason}")
            report.append("")
        
        return "\n".join(report)

