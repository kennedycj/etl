"""Test Stage 4: Deduplication - Check cleansed transactions against database."""

import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import pandas as pd

from finance_app.database.connection import create_database_engine, get_session
from finance_app.agents.data_curation.deduplication import deduplicate_transactions
from finance_app.agents.data_curation.validation import detect_delimiter
from finance_app.agents.data_curation.cleansing import parse_date, clean_amount, normalize_description
from finance_app.importers.tsv_importer import get_or_create_account


def parse_cleansed_csv_to_transactions(session, cleansed_file_path: str) -> list:
    """Parse cleansed CSV file into transaction dictionaries for deduplication.
    
    Args:
        session: Database session
        cleansed_file_path: Path to cleansed CSV file
        
    Returns:
        List of transaction dictionaries with account_id, transaction_date, amount, description
    """
    delimiter = detect_delimiter(cleansed_file_path)
    
    # Read cleansed CSV
    df = pd.read_csv(cleansed_file_path, delimiter=delimiter, dtype=str, keep_default_na=False)
    
    transactions = []
    
    # Find columns
    date_col = None
    amount_col = None
    desc_col = None
    account_name_col = None
    
    # Try parsed columns first (from cleansing stage)
    if '_parsed_date' in df.columns:
        date_col = '_parsed_date'
    else:
        date_cols = [col for col in df.columns if 'date' in col.lower()]
        if date_cols:
            date_col = date_cols[0]
    
    if '_parsed_amount' in df.columns:
        amount_col = '_parsed_amount'
    else:
        amount_cols = [col for col in df.columns if 'amount' in col.lower()]
        if amount_cols:
            amount_col = amount_cols[0]
    
    desc_cols = [col for col in df.columns if any(word in col.lower() for word in ['description', 'memo', 'detail'])]
    if desc_cols:
        desc_col = desc_cols[0]
    
    account_name_cols = [col for col in df.columns if 'account' in col.lower() and 'name' in col.lower()]
    if account_name_cols:
        account_name_col = account_name_cols[0]
    
    if not date_col or not amount_col:
        raise ValueError(f"Could not find date and/or amount columns in {cleansed_file_path}")
    
    if not account_name_col:
        raise ValueError(f"Could not find account name column in {cleansed_file_path}")
    
    # Process each row
    for idx, row in df.iterrows():
        try:
            # Get account
            account_name = str(row.get(account_name_col, '')).strip()
            if not account_name:
                continue
            
            account, _ = get_or_create_account(session, account_name)
            account_id = str(account.id)
            
            # Parse date (handle both string and datetime)
            date_val = row.get(date_col)
            if pd.isna(date_val):
                continue
            if isinstance(date_val, str):
                transaction_date = parse_date(date_val)
            elif isinstance(date_val, pd.Timestamp):
                transaction_date = date_val.to_pydatetime()
            else:
                transaction_date = date_val  # Already a datetime
            if transaction_date is None or not isinstance(transaction_date, datetime):
                continue
            
            # Parse amount
            amount_val = row.get(amount_col)
            if pd.isna(amount_val):
                continue
            if isinstance(amount_val, str):
                amount = clean_amount(amount_val)
            else:
                amount = Decimal(str(amount_val))
            if amount is None:
                continue
            
            # Get description
            description = str(row.get(desc_col, '')).strip() if desc_col else ''
            description = normalize_description(description)
            
            transactions.append({
                'account_id': account_id,
                'transaction_date': transaction_date,
                'amount': amount,
                'description': description,
                '_row_data': row.to_dict()  # Keep original row data for reference
            })
        except Exception as e:
            print(f"Warning: Error parsing row {idx + 1}: {e}")
            continue
    
    return transactions


def test_pipeline_stage_4(cleansed_file_path: str, database_url: str):
    """Test Stage 4: Deduplication"""
    print("\n" + "="*60)
    print("STAGE 4: DEDUPLICATION")
    print("="*60)
    print(f"\nCleansed file: {cleansed_file_path}")
    print(f"Database: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    
    # Connect to database
    engine = create_database_engine(database_url)
    session = get_session(engine)
    
    try:
        # Parse cleansed CSV to transactions
        print("\n[1/3] Parsing cleansed CSV file...")
        transactions_data = parse_cleansed_csv_to_transactions(session, cleansed_file_path)
        print(f"  Parsed {len(transactions_data)} transactions")
        
        if not transactions_data:
            print("\n[ERROR] No valid transactions found in cleansed file")
            return
        
        # Run deduplication
        print("\n[2/3] Checking for duplicates against database...")
        result = deduplicate_transactions(session, transactions_data)
        
        # Report results
        print("\n[3/3] Deduplication Results:")
        print("="*60)
        report = result['deduplication_report']
        print(f"  Total transactions processed: {report['total_processed']}")
        print(f"  ✓ New transactions (to insert): {report['new_count']}")
        print(f"  ✗ Exact duplicates (skip): {report['exact_duplicate_count']}")
        print(f"  ⚠  Fuzzy duplicates (review): {report['fuzzy_duplicate_count']}")
        
        if result['exact_duplicates']:
            print(f"\n  Exact Duplicates ({len(result['exact_duplicates'])}):")
            for dup in result['exact_duplicates'][:5]:  # Show first 5
                txn = dup['transaction_data']
                print(f"    - {txn['transaction_date'].strftime('%Y-%m-%d')} | ${txn['amount']} | {txn['description'][:50]}")
            if len(result['exact_duplicates']) > 5:
                print(f"    ... and {len(result['exact_duplicates']) - 5} more")
        
        if result['fuzzy_duplicates']:
            print(f"\n  Fuzzy Duplicates ({len(result['fuzzy_duplicates'])}):")
            for dup in result['fuzzy_duplicates'][:5]:  # Show first 5
                txn = dup['transaction_data']
                confidence = dup.get('confidence', 0)
                print(f"    - {txn['transaction_date'].strftime('%Y-%m-%d')} | ${txn['amount']} | {txn['description'][:50]} (confidence: {confidence:.2f})")
            if len(result['fuzzy_duplicates']) > 5:
                print(f"    ... and {len(result['fuzzy_duplicates']) - 5} more")
        
        print("\n[OK] Deduplication complete!")
        return result
        
    except Exception as e:
        print(f"\n[ERROR] Deduplication failed: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_deduplication.py <cleansed_file_path> <database_url>")
        print("\nExample:")
        print('  python test_deduplication.py "archive/processed/boa/2025/cleansed_..." "postgresql://user:pass@localhost/finance"')
        print("\nOr use environment variable:")
        print('  $env:DATABASE_URL="postgresql://user:pass@localhost/finance"')
        print('  python test_deduplication.py "archive/processed/boa/2025/cleansed_..."')
        sys.exit(1)
    
    cleansed_file = sys.argv[1]
    database_url = sys.argv[2] if len(sys.argv) > 2 else os.getenv("DATABASE_URL")
    
    if not database_url:
        print("[ERROR] Database URL required (provide as argument or set DATABASE_URL env var)")
        sys.exit(1)
    
    if not Path(cleansed_file).exists():
        print(f"[ERROR] File not found: {cleansed_file}")
        sys.exit(1)
    
    test_pipeline_stage_4(cleansed_file, database_url)

