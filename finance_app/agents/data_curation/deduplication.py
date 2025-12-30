"""Deduplication tools - identify and handle duplicate transactions."""

import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

from finance_app.database.models import TransactionModel, AccountModel


class DuplicateTransaction:
    """Represents a duplicate transaction."""
    def __init__(self, transaction_id: str, reason: str, confidence: float):
        self.transaction_id = transaction_id
        self.reason = reason
        self.confidence = confidence


def calculate_transaction_signature(account_id: str, date: datetime, amount: Decimal, 
                                   description: str) -> str:
    """Calculate unique signature for a transaction.
    
    Args:
        account_id: Account UUID as string
        date: Transaction date
        amount: Transaction amount
        description: Transaction description (normalized)
        
    Returns:
        SHA-256 hash signature
    """
    # Normalize description (lowercase, remove extra whitespace)
    normalized_desc = " ".join(description.lower().split()) if description else ""
    
    # Create signature string
    sig_string = f"{account_id}|{date.isoformat()}|{amount}|{normalized_desc}"
    
    return hashlib.sha256(sig_string.encode('utf-8')).hexdigest()


def calculate_description_hash(description: str) -> str:
    """Calculate hash of normalized description.
    
    Args:
        description: Transaction description
        
    Returns:
        MD5 hash (shorter, good enough for description matching)
    """
    normalized = " ".join(str(description).lower().split()) if description else ""
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def find_exact_duplicates(session: Session, account_id: str, date: datetime, 
                         amount: Decimal, description: str) -> List[str]:
    """Find exact duplicate transactions in database.
    
    Args:
        session: Database session
        account_id: Account UUID
        date: Transaction date
        amount: Transaction amount
        description: Transaction description
        
    Returns:
        List of transaction IDs that are exact duplicates
    """
    signature = calculate_transaction_signature(account_id, date, amount, description)
    desc_hash = calculate_description_hash(description)
    
    # For exact matching, we can query by the components
    # Since we don't store signatures, query by components
    duplicates = session.query(TransactionModel.id).filter(
        TransactionModel.account_id == account_id,
        TransactionModel.transaction_date == date,
        TransactionModel.amount == amount,
        func.md5(TransactionModel.description) == desc_hash
    ).all()
    
    return [str(txn_id[0]) for txn_id in duplicates]


def find_fuzzy_duplicates(session: Session, account_id: str, date: datetime,
                         amount: Decimal, description: str, 
                         date_tolerance_days: int = 3,
                         amount_tolerance: Decimal = Decimal('0.50')) -> List[Tuple[str, float]]:
    """Find fuzzy duplicate transactions (similar but not exact).
    
    Args:
        session: Database session
        account_id: Account UUID
        date: Transaction date
        amount: Transaction amount
        description: Transaction description
        date_tolerance_days: Days within which to consider duplicate
        amount_tolerance: Amount difference tolerance
        
    Returns:
        List of tuples: (transaction_id, confidence_score)
    """
    date_start = date - timedelta(days=date_tolerance_days)
    date_end = date + timedelta(days=date_tolerance_days)
    amount_min = amount - amount_tolerance
    amount_max = amount + amount_tolerance
    
    desc_hash = calculate_description_hash(description)
    
    candidates = session.query(TransactionModel.id, TransactionModel.description).filter(
        TransactionModel.account_id == account_id,
        TransactionModel.transaction_date >= date_start,
        TransactionModel.transaction_date <= date_end,
        TransactionModel.amount >= amount_min,
        TransactionModel.amount <= amount_max
    ).all()
    
    results = []
    for txn_id, txn_desc in candidates:
        candidate_hash = calculate_description_hash(txn_desc)
        # Calculate similarity confidence based on description match
        if candidate_hash == desc_hash:
            confidence = 0.9  # Same description, high confidence
        elif description.lower() in txn_desc.lower() or txn_desc.lower() in description.lower():
            confidence = 0.7  # One contains the other
        else:
            confidence = 0.5  # Similar amount/date but different description
        
        results.append((str(txn_id), confidence))
    
    return results


def deduplicate_transactions(session: Session, transactions_data: List[Dict]) -> Dict:
    """Deduplicate a list of transactions against database.
    
    Args:
        session: Database session
        transactions_data: List of transaction dictionaries with:
            - account_id (UUID string)
            - transaction_date (datetime)
            - amount (Decimal)
            - description (str)
            - (other fields...)
            
    Returns:
        Dictionary with:
        - new_transactions: Transactions to insert
        - exact_duplicates: Exact duplicate transactions (skip)
        - fuzzy_duplicates: Fuzzy matches (review needed)
        - deduplication_report: Detailed statistics
    """
    new_transactions = []
    exact_duplicates = []
    fuzzy_duplicates = []
    
    for txn_data in transactions_data:
        account_id = txn_data['account_id']
        date = txn_data['transaction_date']
        amount = txn_data['amount']
        description = txn_data['description']
        
        # Check for exact duplicates
        exact_matches = find_exact_duplicates(session, account_id, date, amount, description)
        
        if exact_matches:
            exact_duplicates.append({
                'transaction_data': txn_data,
                'existing_transaction_ids': exact_matches,
                'match_type': 'exact'
            })
            continue
        
        # Check for fuzzy duplicates
        fuzzy_matches = find_fuzzy_duplicates(session, account_id, date, amount, description)
        
        if fuzzy_matches:
            # If high confidence fuzzy match, treat as duplicate
            high_confidence = [m for m in fuzzy_matches if m[1] >= 0.8]
            if high_confidence:
                fuzzy_duplicates.append({
                    'transaction_data': txn_data,
                    'existing_transaction_ids': [m[0] for m in high_confidence],
                    'match_type': 'fuzzy_high_confidence',
                    'confidence': high_confidence[0][1]
                })
            else:
                fuzzy_duplicates.append({
                    'transaction_data': txn_data,
                    'existing_transaction_ids': [m[0] for m in fuzzy_matches],
                    'match_type': 'fuzzy_low_confidence',
                    'confidence': max([m[1] for m in fuzzy_matches]) if fuzzy_matches else 0
                })
            continue
        
        # No duplicates found - this is a new transaction
        new_transactions.append(txn_data)
    
    return {
        'new_transactions': new_transactions,
        'exact_duplicates': exact_duplicates,
        'fuzzy_duplicates': fuzzy_duplicates,
        'deduplication_report': {
            'total_processed': len(transactions_data),
            'new_count': len(new_transactions),
            'exact_duplicate_count': len(exact_duplicates),
            'fuzzy_duplicate_count': len(fuzzy_duplicates)
        }
    }


if __name__ == "__main__":
    print("Deduplication module - use through data curation agent")

