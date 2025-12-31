"""Add mortgage balance to the ledger.

This script processes mortgage statements (PDF or CSV) and adds the current
principal balance to the ledger as a liability.
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

from finance_app.agents.ledger.mortgage_processor import (
    extract_mortgage_data_from_pdf, create_mortgage_csv_template,
    load_mortgage_balance_from_csv, create_mortgage_ledger_entry
)
from finance_app.agents.data_curation.archive_scanner import get_archive_root


def get_archive_paths():
    """Get archive paths."""
    archive_root = get_archive_root()
    mortgage_dir = archive_root / "00_raw" / "bank" / "us_bank" / "mortgage"
    ledger_dir = archive_root / "20_ledger"
    return archive_root, mortgage_dir, ledger_dir


def main():
    """Main function to add mortgage balance to ledger."""
    archive_root, mortgage_dir, ledger_dir = get_archive_paths()
    
    print("="*60)
    print("Adding Mortgage Balance to Ledger")
    print("="*60)
    
    if not mortgage_dir.exists():
        print(f"Error: Mortgage directory not found at {mortgage_dir}")
        return
    
    # Try PDF extraction first
    pdf_files = list(mortgage_dir.glob('*.pdf'))
    mortgage_data = None
    
    if pdf_files:
        # Use the most recent PDF
        pdf_file = sorted(pdf_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        print(f"\nAttempting to extract data from PDF: {pdf_file.name}")
        mortgage_data = extract_mortgage_data_from_pdf(pdf_file)
        
        if mortgage_data:
            print(f"[OK] Extracted mortgage data from PDF")
            print(f"  Principal balance: ${mortgage_data['principal_balance']:,.2f}")
            if mortgage_data.get('interest_rate'):
                print(f"  Interest rate: {mortgage_data['interest_rate']*100:.2f}%")
            if mortgage_data.get('statement_date'):
                print(f"  Statement date: {mortgage_data['statement_date'].strftime('%Y-%m-%d')}")
        else:
            print("[FAILED] PDF extraction failed")
    
    # Fall back to CSV if PDF extraction failed
    if not mortgage_data:
        print("\nFalling back to CSV entry...")
        csv_path = mortgage_dir / "mortgage_balance.csv"
        
        if not csv_path.exists():
            print(f"\nCreating mortgage balance template...")
            create_mortgage_csv_template(mortgage_dir)
            print(f"[OK] Template created: {csv_path}")
            print("\nPlease fill in the CSV with your mortgage balance.")
            print("Required columns: statement_date, principal_balance, interest_rate")
            print("  - statement_date: Statement date (YYYY-MM-DD)")
            print("  - principal_balance: Outstanding principal balance")
            print("  - interest_rate: Interest rate as decimal (e.g., 0.0425 for 4.25%)")
            print("\nAfter filling in the CSV, run this script again.")
            return
        
        mortgage_data = load_mortgage_balance_from_csv(csv_path)
        if not mortgage_data:
            print("No mortgage data found in CSV. Please fill in the template.")
            return
        
        print(f"[OK] Loaded mortgage data from CSV")
        print(f"  Principal balance: ${mortgage_data['principal_balance']:,.2f}")
    
    # Create ledger entry
    print(f"\nCreating ledger entry...")
    ledger_entry = create_mortgage_ledger_entry(mortgage_data, institution="USBank")
    
    # Load existing ledger - use the most complete one available
    ledger_paths = [
        ledger_dir / "ledger_with_heloc.csv",  # Most complete (includes HELOC and CDs)
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
    
    # Remove any existing mortgage balance entries to avoid duplicates
    mortgage_mask = ledger_df['account'].str.contains('Liabilities:Mortgage:', case=False, na=False)
    old_mortgage_count = mortgage_mask.sum()
    if old_mortgage_count > 0:
        print(f"Removing {old_mortgage_count} existing mortgage entries to avoid duplicates")
        # But keep mortgage payment transactions - only remove balance entries
        # Balance entries typically have descriptions like "Mortgage balance as of..."
        balance_mask = ledger_df['description'].str.contains('balance as of', case=False, na=False)
        combined_mask = mortgage_mask & balance_mask
        if combined_mask.sum() > 0:
            print(f"Removing {combined_mask.sum()} mortgage balance entries")
            ledger_df = ledger_df[~combined_mask].copy()
            print(f"Ledger now has {len(ledger_df)} entries (after removing old mortgage balances)")
    
    # Add mortgage balance entry
    new_row = pd.DataFrame([ledger_entry])
    new_row['date'] = pd.to_datetime(new_row['date'])
    
    updated_ledger = pd.concat([ledger_df, new_row], ignore_index=True)
    updated_ledger = updated_ledger.sort_values('date')
    
    # Save updated ledger
    output_path = ledger_dir / "ledger_with_mortgage.csv"
    updated_ledger.to_csv(output_path, index=False)
    
    print(f"\n[OK] Added mortgage balance to ledger")
    print(f"Updated ledger saved to: {output_path.name}")
    print(f"Total entries: {len(updated_ledger)} (was {len(ledger_df)})")
    
    # Show mortgage summary
    mortgage_entries = updated_ledger[updated_ledger['account'].str.contains('Liabilities:Mortgage:', case=False, na=False)]
    mortgage_balance = mortgage_entries['amount'].sum()
    
    print("\n" + "="*60)
    print("MORTGAGE SUMMARY")
    print("="*60)
    print(f"Principal balance: ${abs(mortgage_balance):,.2f}")
    print(f"  (Negative balance = liability)")
    if mortgage_data.get('interest_rate'):
        print(f"Interest rate: {mortgage_data['interest_rate']*100:.2f}%")
    if mortgage_data.get('maturity_date'):
        print(f"Maturity date: {mortgage_data['maturity_date'].strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    main()

