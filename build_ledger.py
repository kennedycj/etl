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

