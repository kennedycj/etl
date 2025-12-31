"""Build general ledger from processed transaction files."""

import sys
from pathlib import Path
from finance_app.agents.ledger.ledger_builder import LedgerBuilder

if __name__ == "__main__":
    import os
    
    archive_root = os.getenv("FINANCE_ARCHIVE_ROOT")
    archive_path = Path(archive_root) if archive_root else None
    
    print("Building ledger from processed transaction files...")
    print(f"Archive root: {archive_path or 'default'}")
    
    builder = LedgerBuilder(archive_path)
    
    # Load and process transactions
    builder.build_ledger_from_processed_files()
    
    print(f"\nProcessed {len(builder.entries)} ledger entries")
    
    # Export to various formats
    print("\nExporting ledger...")
    builder.export_to_csv()
    builder.export_to_beancount()
    builder.export_to_ledger_cli()
    
    if builder.opening_balances:
        builder.save_opening_balances()
    
    if builder.adjustments:
        builder.save_adjustments()
    
    print(f"\n[OK] Ledger exported to: {builder.ledger_path}")
    print("  - ledger.csv (CSV format)")
    print("  - ledger.beancount (Beancount format)")
    print("  - ledger.dat (Ledger CLI format)")
    print("  - opening_balances.csv")
    print("  - adjustments.csv")
    
    # Run account matching to reconcile credit card payments
    print("\n" + "="*60)
    print("Reconciling credit card payments...")
    print("="*60)
    
    from finance_app.agents.ledger.account_matcher import AccountMatcher
    
    ledger_csv_path = builder.ledger_path / "ledger.csv"
    matcher = AccountMatcher(ledger_csv_path, max_date_diff_days=3)
    matches = matcher.find_credit_card_payments()
    
    if matches:
        print(f"Found {len(matches)} matched credit card payment pairs")
        
        # Create corrected entries
        corrected_df = matcher.create_corrected_entries()
        corrected_path = builder.ledger_path / "ledger_corrected.csv"
        corrected_df.to_csv(corrected_path, index=False)
        print(f"  Corrected entries: {len(corrected_df)} entries")
        
        # Create reconciled ledger (original with corrections applied)
        reconciled_path = builder.ledger_path / "ledger_reconciled.csv"
        reconciled_df = matcher.create_reconciled_ledger(reconciled_path)
        print(f"  Reconciled ledger: {len(reconciled_df)} entries (original: {len(matcher.ledger_df)} entries)")
        print(f"    Removed {len(matcher.ledger_df) - len(reconciled_df) + len(corrected_df)} incorrect entries")
        print(f"    Added {len(corrected_df)} corrected entries")
        
        # Generate reconciliation report
        report_path = builder.ledger_path / "reconciliation_report.txt"
        report = matcher.generate_reconciliation_report()
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n[OK] Reconciliation complete:")
        print(f"  - Corrected entries: {corrected_path}")
        print(f"  - Reconciled ledger: {reconciled_path}")
        print(f"  - Report: {report_path}")
    else:
        print("No credit card payment matches found.")

