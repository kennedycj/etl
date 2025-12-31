"""Reconcile and match transactions across accounts."""

import sys
from pathlib import Path
from finance_app.agents.ledger.account_matcher import AccountMatcher

def get_ledger_path():
    """Get the path to the ledger CSV file."""
    archive_root = Path.home() / "Documents" / "finance_archive"
    ledger_path = archive_root / "20_ledger" / "ledger.csv"
    
    import os
    if "FINANCE_ARCHIVE_ROOT" in os.environ:
        archive_root = Path(os.environ["FINANCE_ARCHIVE_ROOT"])
        ledger_path = archive_root / "20_ledger" / "ledger.csv"
    
    return ledger_path

def main():
    """Main reconciliation function."""
    ledger_path = get_ledger_path()
    
    if not ledger_path.exists():
        print(f"Error: Ledger file not found at {ledger_path}")
        sys.exit(1)
    
    print("Loading ledger and finding credit card payment matches...")
    matcher = AccountMatcher(ledger_path, max_date_diff_days=3)
    
    matches = matcher.find_credit_card_payments()
    
    print(f"\nFound {len(matches)} matched credit card payment pairs")
    
    # Generate report
    report = matcher.generate_reconciliation_report()
    print("\n" + report)
    
    # Create corrected entries
    if matches:
        corrected_df = matcher.create_corrected_entries()
        
        # Save corrected entries
        output_path = ledger_path.parent / "ledger_corrected.csv"
        corrected_df.to_csv(output_path, index=False)
        print(f"\n[OK] Corrected entries saved to: {output_path}")
        print(f"  Total corrected entries: {len(corrected_df)}")
        
        # Show sample
        print("\nSample corrected entries:")
        print(corrected_df[['date', 'description', 'account', 'amount']].head(10).to_string())

if __name__ == "__main__":
    main()

