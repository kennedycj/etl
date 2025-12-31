"""Add HELOC transactions to the ledger.

HELOC accounts are liabilities - transactions affect the outstanding balance.
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

from finance_app.agents.ledger.heloc_processor import (
    create_heloc_csv_template, load_heloc_transactions_from_csv,
    create_heloc_ledger_entries
)
from finance_app.agents.data_curation.archive_scanner import get_archive_root


def get_archive_paths():
    """Get archive paths."""
    archive_root = get_archive_root()
    heloc_dir = archive_root / "00_raw" / "bank" / "us_bank" / "heloc"
    ledger_dir = archive_root / "20_ledger"
    return archive_root, heloc_dir, ledger_dir


def main():
    """Main function to add HELOC to ledger."""
    archive_root, heloc_dir, ledger_dir = get_archive_paths()
    
    print("="*60)
    print("Adding HELOC Transactions to Ledger")
    print("="*60)
    
    if not heloc_dir.exists():
        print(f"Error: HELOC directory not found at {heloc_dir}")
        return
    
    # Prioritize CSV files over PDF extraction
    csv_files = list(heloc_dir.glob('*.csv'))
    
    if csv_files:
        # Use the first CSV file found (or could use most recent)
        csv_path = csv_files[0]
        print(f"\nLoading HELOC transactions from CSV: {csv_path.name}")
        try:
            heloc_df = load_heloc_transactions_from_csv(csv_path)
            if len(heloc_df) == 0:
                print("No valid transactions found in CSV.")
                return
            print(f"[OK] Loaded {len(heloc_df)} HELOC transactions from CSV")
        except Exception as e:
            print(f"[ERROR] Error loading CSV: {e}")
            import traceback
            traceback.print_exc()
            return
    else:
        # Fall back to PDF extraction if no CSV found
        print("\nNo CSV files found. Attempting to extract transactions from PDF files...")
        from finance_app.agents.ledger.heloc_processor import extract_heloc_transactions_from_pdf
        
        pdf_files = list(heloc_dir.glob('*.pdf'))
        all_transactions = []
        
        for pdf_file in pdf_files:
            print(f"  Processing: {pdf_file.name}")
            transactions = extract_heloc_transactions_from_pdf(pdf_file)
            if transactions:
                print(f"    [OK] Extracted {len(transactions)} transactions")
                all_transactions.extend(transactions)
            else:
                print(f"    [FAILED] No transactions extracted")
        
        if all_transactions:
            print(f"\n[OK] Successfully extracted {len(all_transactions)} transactions from PDFs")
            heloc_df = pd.DataFrame(all_transactions)
        else:
            print("\nPDF extraction failed or no transactions found.")
            print(f"\nCreating HELOC transaction template...")
            csv_path = create_heloc_csv_template(heloc_dir)
            print(f"[OK] Template created: {csv_path}")
            print("\nPlease fill in the CSV with your HELOC transactions.")
            print("Required columns: date, description, amount")
            print("  - date: Transaction date (YYYY-MM-DD or MM/DD/YYYY)")
            print("  - description: Transaction description")
            print("  - amount: Positive for charges/draws, negative for payments")
            print("\nAfter filling in the CSV, run this script again.")
            return
    
    # Create ledger entries
    print(f"\nCreating ledger entries...")
    ledger_entries = create_heloc_ledger_entries(heloc_df, institution="USBank")
    print(f"[OK] Created {len(ledger_entries)} ledger entries")
    
    # Load existing ledger - use the most complete one available
    # Priority: ledger_with_heloc > ledger_with_cds > ledger_reconciled > ledger
    ledger_paths = [
        ledger_dir / "ledger_with_heloc.csv",  # Most complete (includes HELOC)
        ledger_dir / "ledger_with_cds.csv",    # Includes CDs
        ledger_dir / "ledger_reconciled.csv",  # Base reconciled ledger
        ledger_dir / "ledger.csv"              # Original ledger
    ]
    
    ledger_path = None
    for path in ledger_paths:
        if path.exists():
            ledger_path = path
            break
    
    if not ledger_path:
        print(f"Error: No ledger file found in {ledger_dir}")
        print("Please run build_ledger.py first.")
        return
    
    print(f"Loading existing ledger from: {ledger_path.name}")
    ledger_df = pd.read_csv(ledger_path)
    ledger_df['date'] = pd.to_datetime(ledger_df['date'])
    ledger_df['amount'] = pd.to_numeric(ledger_df['amount'], errors='coerce')
    
    print(f"Loaded {len(ledger_df)} existing ledger entries")
    
    # Remove any existing HELOC entries to avoid duplicates
    heloc_account = "Liabilities:HELOC:USBank"
    heloc_mask = ledger_df['account'].str.contains('HELOC', case=False, na=False)
    old_heloc_count = heloc_mask.sum()
    if old_heloc_count > 0:
        print(f"Removing {old_heloc_count} existing HELOC entries to avoid duplicates")
        ledger_df = ledger_df[~heloc_mask].copy()
        print(f"Ledger now has {len(ledger_df)} entries (after removing old HELOC)")
    
    # Convert HELOC entries to DataFrame format
    new_rows = []
    for entry in ledger_entries:
        # Create double-entry: HELOC liability and offsetting account
        date_val = entry['date']
        # Ensure date is datetime object
        if isinstance(date_val, str):
            date_val = pd.to_datetime(date_val)
        date_str = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)
        
        # Entry 1: HELOC liability side
        new_rows.append({
            'date': date_str,
            'description': entry['description'],
            'account': entry['account'],
            'amount': entry['amount'],  # Liability: charges negative, payments positive
            'source_file': entry['source_file'],
            'transaction_id': ''
        })
        
        # Entry 2: Offsetting account (checking or expense)
        new_rows.append({
            'date': date_str,
            'description': entry['description'],
            'account': entry['offset_account'],
            'amount': entry['offset_amount'],  # Opposite side
            'source_file': entry['source_file'],
            'transaction_id': ''
        })
    
    # Append HELOC entries
    heloc_df_new = pd.DataFrame(new_rows)
    # Ensure date column is datetime before concatenating
    heloc_df_new['date'] = pd.to_datetime(heloc_df_new['date'])
    updated_ledger = pd.concat([ledger_df, heloc_df_new], ignore_index=True)
    updated_ledger = updated_ledger.sort_values('date')
    
    # Save updated ledger - always use ledger_with_heloc.csv as the consolidated file
    # (this will include CDs if they were added first, or we can merge them)
    output_path = ledger_dir / "ledger_with_heloc.csv"
    
    # If we're building on ledger_with_cds, the output will include both
    # If we're building on ledger_with_heloc, we're updating it
    updated_ledger.to_csv(output_path, index=False)
    
    print(f"\n[OK] Added {len(ledger_entries)} HELOC transactions to ledger")
    print(f"Updated ledger saved to: {output_path}")
    print(f"Total entries: {len(updated_ledger)} (was {len(ledger_df)})")
    
    # Show HELOC summary
    heloc_entries_df = heloc_df_new[heloc_df_new['account'].str.contains('HELOC', case=False, na=False)]
    heloc_balance = heloc_entries_df['amount'].sum()
    
    print("\n" + "="*60)
    print("HELOC SUMMARY")
    print("="*60)
    print(f"Total transactions: {len(ledger_entries)}")
    print(f"HELOC balance change: ${heloc_balance:,.2f}")
    print(f"  (Negative = liability increased, Positive = liability decreased)")
    
    # Show sample transactions
    print(f"\nSample transactions (first 5):")
    sample = heloc_df.head(5)[['date', 'description', 'amount']]
    print(sample.to_string(index=False))


if __name__ == "__main__":
    main()

