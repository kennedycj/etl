"""Add CD balances to the ledger.

This script processes CD PDFs (or manually entered balances) and adds them
as asset entries to the reconciled ledger.
"""

import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import pandas as pd

from finance_app.agents.ledger.cd_processor import (
    find_latest_cd_statements, load_cd_balances, create_cd_ledger_entries,
    match_cd_transactions
)
from finance_app.agents.data_curation.archive_scanner import get_archive_root


def get_archive_paths():
    """Get archive paths."""
    archive_root = get_archive_root()
    cd_dir = archive_root / "00_raw" / "bank" / "bank_of_america" / "cd"
    ledger_dir = archive_root / "20_ledger"
    return archive_root, cd_dir, ledger_dir




def load_cd_balances_from_csv(csv_path: Path) -> pd.DataFrame:
    """Load CD balances from manually created CSV."""
    df = pd.read_csv(csv_path)
    # Ensure required columns exist
    required = ['cd_id', 'balance']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    # Filter out rows without balances
    df = df[df['balance'].notna() & (df['balance'] != '')].copy()
    df['balance'] = pd.to_numeric(df['balance'], errors='coerce')
    df = df[df['balance'].notna()]
    
    return df


def main():
    """Main function to add CDs to ledger."""
    archive_root, cd_dir, ledger_dir = get_archive_paths()
    
    print("="*60)
    print("Adding CDs to Ledger")
    print("="*60)
    
    # Try to load CD balances from PDFs
    print("\nAttempting to extract CD balances from PDFs...")
    try:
        cd_df = load_cd_balances(cd_dir, "BankOfAmerica")
        if len(cd_df) == 0:
            raise ValueError("No CD balances extracted from PDFs")
        print(f"[OK] Extracted {len(cd_df)} CD balances from PDFs")
    except Exception as e:
        print(f"[FAILED] PDF extraction failed: {e}")
        print("\nFalling back to manual CSV entry...")
        
        # Create template or use existing CSV
        csv_path = cd_dir.parent / "cd_balances.csv"
        
        if not csv_path.exists():
            # Create template
            from finance_app.agents.ledger.cd_processor import parse_cd_filename
            latest = find_latest_cd_statements(cd_dir)
            template_data = []
            for cd_id, pdf_path in latest.items():
                filename_info = parse_cd_filename(pdf_path.name)
                template_data.append({
                    'cd_id': cd_id,
                    'balance': '',  # User fills this in
                    'statement_date': filename_info['end_date'].strftime('%Y-%m-%d') if filename_info else '',
                    'next_maturity_date': '',
                    'interest_rate': '',
                    'apy': ''
                })
            
            template_df = pd.DataFrame(template_data)
            template_df.to_csv(csv_path, index=False)
            print(f"Created template: {csv_path}")
            print("Please fill in the CD balances and run this script again.")
            return
        
        if not csv_path.exists():
            print("Please create cd_balances.csv manually with columns: cd_id, balance, statement_date")
            return
        
        cd_df = load_cd_balances_from_csv(csv_path)
        if len(cd_df) == 0:
            print("No CD balances found in CSV. Please fill in the template.")
            return
        print(f"[OK] Loaded {len(cd_df)} CD balances from CSV")
    
    # Get statement date (use latest or current date)
    if 'statement_date' in cd_df.columns:
        statement_date = pd.to_datetime(cd_df['statement_date']).max().to_pydatetime()
    else:
        statement_date = datetime.now()
    
    # Create ledger entries for CD balances
    print(f"\nCreating ledger entries for {len(cd_df)} CDs...")
    cd_entries = create_cd_ledger_entries(cd_df, statement_date, "BankOfAmerica")
    
    # Load existing ledger - use the most complete one available
    # Priority: ledger_with_heloc > ledger_reconciled > ledger
    # (ledger_with_cds comes last because that's what we're creating)
    ledger_paths = [
        ledger_dir / "ledger_with_heloc.csv",  # Most complete (includes HELOC)
        ledger_dir / "ledger_reconciled.csv",  # Base reconciled ledger
        ledger_dir / "ledger.csv"              # Original ledger
    ]
    
    ledger_path = None
    for path in ledger_paths:
        if path.exists():
            ledger_path = path
            break
    
    if not ledger_path:
        print(f"Error: No base ledger found in {ledger_dir}")
        print("Please run build_ledger.py first to create the base ledger.")
        return
    
    ledger_df = pd.read_csv(ledger_path)
    ledger_df['date'] = pd.to_datetime(ledger_df['date'])
    ledger_df['amount'] = pd.to_numeric(ledger_df['amount'], errors='coerce')
    print(f"Loaded {len(ledger_df)} entries from {ledger_path.name}")
    
    # Remove any existing CD entries to avoid duplicates
    cd_mask = ledger_df['account'].str.contains('CD:', case=False, na=False)
    old_cd_count = cd_mask.sum()
    if old_cd_count > 0:
        print(f"Removing {old_cd_count} existing CD entries to avoid duplicates")
        ledger_df = ledger_df[~cd_mask].copy()
        print(f"Ledger now has {len(ledger_df)} entries (after removing old CDs)")
    
    # Add CD entries to ledger
    new_rows = []
    for date_str, desc, account, amount, source_file in cd_entries:
        new_rows.append({
            'date': date_str,
            'description': desc,
            'account': account,
            'amount': float(amount),
            'source_file': source_file,
            'transaction_id': ''  # CD entries don't have transaction IDs
        })
    
    # Append CD entries
    cd_df_new = pd.DataFrame(new_rows)
    # Ensure date column is datetime before concatenating
    cd_df_new['date'] = pd.to_datetime(cd_df_new['date'])
    updated_ledger = pd.concat([ledger_df, cd_df_new], ignore_index=True)
    updated_ledger = updated_ledger.sort_values('date')
    
    # Save updated ledger
    # If base was ledger_with_heloc, we should save as ledger_with_heloc to keep everything together
    # Otherwise save as ledger_with_cds
    if 'heloc' in ledger_path.name.lower():
        output_path = ledger_dir / "ledger_with_heloc.csv"
        print(f"\nNote: Saving as ledger_with_heloc.csv (includes both CDs and HELOC)")
    else:
        output_path = ledger_dir / "ledger_with_cds.csv"
    
    updated_ledger.to_csv(output_path, index=False)
    
    print(f"\n[OK] Added {len(cd_entries)} CD entries to ledger")
    print(f"Updated ledger saved to: {output_path}")
    print(f"Total entries: {len(updated_ledger)} (was {len(ledger_df)})")
    
    # Show CD summary
    print("\n" + "="*60)
    print("CD SUMMARY")
    print("="*60)
    print(f"{'CD ID':<10} {'Balance':>15} {'Account':<40}")
    print("-" * 65)
    total_cd_balance = 0
    for _, row in cd_df.iterrows():
        cd_id = row['cd_id']
        balance = row['balance']
        account = f"Assets:BankOfAmerica:CD:{cd_id}"
        total_cd_balance += balance
        print(f"{cd_id:<10} ${balance:>14,.2f} {account:<40}")
    print("-" * 65)
    print(f"{'TOTAL':<10} ${total_cd_balance:>14,.2f}")


if __name__ == "__main__":
    main()

