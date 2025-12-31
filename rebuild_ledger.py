"""Clean and rebuild the complete ledger from scratch.

This script:
1. Removes all existing ledger files
2. Rebuilds the base ledger from processed data
3. Adds CD balances
4. Adds HELOC transactions
5. Adds mortgage balance
6. Shows a summary
"""

import sys
from pathlib import Path
import shutil
from datetime import datetime

from finance_app.agents.data_curation.archive_scanner import get_archive_root


def get_ledger_directory():
    """Get the ledger directory path."""
    archive_root = get_archive_root()
    return archive_root / "20_ledger"


def remove_ledger_files():
    """Remove all existing ledger CSV files."""
    ledger_dir = get_ledger_directory()
    
    if not ledger_dir.exists():
        print(f"Ledger directory does not exist: {ledger_dir}")
        return 0
    
    ledger_files = list(ledger_dir.glob("*.csv"))
    
    if not ledger_files:
        print("No ledger files found to remove.")
        return 0
    
    print("="*70)
    print("REMOVING EXISTING LEDGER FILES")
    print("="*70)
    
    removed_count = 0
    failed_files = []
    
    for ledger_file in ledger_files:
        try:
            print(f"  Removing: {ledger_file.name}")
            ledger_file.unlink()
            removed_count += 1
        except PermissionError:
            print(f"    [WARNING] Cannot remove {ledger_file.name} - file is locked (may be open in Excel)")
            failed_files.append(ledger_file.name)
        except Exception as e:
            print(f"    [WARNING] Error removing {ledger_file.name}: {e}")
            failed_files.append(ledger_file.name)
    
    print(f"\n[OK] Removed {removed_count} ledger file(s)")
    if failed_files:
        print(f"[WARNING] Could not remove {len(failed_files)} file(s): {', '.join(failed_files)}")
        print("  Please close these files and run the script again, or delete them manually.")
    
    return removed_count


def rebuild_base_ledger():
    """Rebuild the base ledger from processed data."""
    print("\n" + "="*70)
    print("REBUILDING BASE LEDGER")
    print("="*70)
    
    try:
        # Import and run build_ledger as a module
        import build_ledger
        # build_ledger.py doesn't have a main() function, it runs directly
        # So we need to execute it differently
        import subprocess
        import sys
        
        result = subprocess.run([sys.executable, "build_ledger.py"], 
                              capture_output=False, 
                              text=True)
        
        if result.returncode == 0:
            print("\n[OK] Base ledger rebuilt successfully")
            return True
        else:
            print(f"\n[ERROR] build_ledger.py exited with code {result.returncode}")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Failed to rebuild base ledger: {e}")
        import traceback
        traceback.print_exc()
        return False


def add_cds():
    """Add CD balances to the ledger."""
    print("\n" + "="*70)
    print("ADDING CD BALANCES")
    print("="*70)
    
    try:
        import subprocess
        import sys
        
        result = subprocess.run([sys.executable, "add_cds_to_ledger.py"], 
                              capture_output=False, 
                              text=True)
        
        if result.returncode == 0:
            print("\n[OK] CD balances added successfully")
            return True
        else:
            print(f"\n[WARNING] add_cds_to_ledger.py exited with code {result.returncode}")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Failed to add CD balances: {e}")
        import traceback
        traceback.print_exc()
        return False


def add_heloc():
    """Add HELOC transactions to the ledger."""
    print("\n" + "="*70)
    print("ADDING HELOC TRANSACTIONS")
    print("="*70)
    
    try:
        import subprocess
        import sys
        
        result = subprocess.run([sys.executable, "add_heloc_to_ledger.py"], 
                              capture_output=False, 
                              text=True)
        
        if result.returncode == 0:
            print("\n[OK] HELOC transactions added successfully")
            return True
        else:
            print(f"\n[WARNING] add_heloc_to_ledger.py exited with code {result.returncode}")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Failed to add HELOC transactions: {e}")
        import traceback
        traceback.print_exc()
        return False


def add_mortgage():
    """Add mortgage balance to the ledger."""
    print("\n" + "="*70)
    print("ADDING MORTGAGE BALANCE")
    print("="*70)
    
    try:
        import subprocess
        import sys
        
        result = subprocess.run([sys.executable, "add_mortgage_to_ledger.py"], 
                              capture_output=False, 
                              text=True)
        
        if result.returncode == 0:
            print("\n[OK] Mortgage balance added successfully")
            return True
        else:
            print(f"\n[WARNING] add_mortgage_to_ledger.py exited with code {result.returncode}")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Failed to add mortgage balance: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_summary():
    """Show a summary of the final ledger."""
    print("\n" + "="*70)
    print("FINAL LEDGER SUMMARY")
    print("="*70)
    
    ledger_dir = get_ledger_directory()
    # Prefer most complete ledger (with mortgage, HELOC, and CDs)
    final_ledger = ledger_dir / "ledger_with_mortgage.csv"
    
    if not final_ledger.exists():
        # Fall back to HELOC ledger if mortgage not available
        final_ledger = ledger_dir / "ledger_with_heloc.csv"
        if not final_ledger.exists():
            print(f"[WARNING] Final ledger file not found")
            return
    
    try:
        import pandas as pd
        df = pd.read_csv(final_ledger)
        
        print(f"\nLedger file: {final_ledger.name}")
        print(f"Total entries: {len(df):,}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        
        # Count by account type
        print(f"\nAccount breakdown:")
        asset_count = len(df[df['account'].str.startswith('Assets:', na=False)])
        liability_count = len(df[df['account'].str.startswith('Liabilities:', na=False)])
        expense_count = len(df[df['account'].str.startswith('Expenses:', na=False)])
        income_count = len(df[df['account'].str.startswith('Income:', na=False)])
        
        print(f"  Assets: {asset_count:,} entries")
        print(f"  Liabilities: {liability_count:,} entries")
        print(f"  Expenses: {expense_count:,} entries")
        print(f"  Income: {income_count:,} entries")
        
        # Check for CDs, HELOC, and Mortgage
        cd_entries = len(df[df['account'].str.contains('CD:', case=False, na=False)])
        heloc_entries = len(df[df['account'].str.contains('HELOC', case=False, na=False)])
        mortgage_entries = len(df[df['account'].str.contains('Liabilities:Mortgage:', case=False, na=False)])
        
        print(f"\nSpecial accounts:")
        print(f"  CD entries: {cd_entries}")
        print(f"  HELOC entries: {heloc_entries}")
        print(f"  Mortgage entries: {mortgage_entries}")
        
        print(f"\n[OK] Ledger rebuild complete!")
        print(f"\nNext steps:")
        print(f"  1. Run: python analyze_assets.py")
        print(f"  2. Run: python analyze_income.py")
        print(f"  3. Run: python analyze_expenses.py")
        
    except Exception as e:
        print(f"[ERROR] Failed to generate summary: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function to clean and rebuild the ledger."""
    print("="*70)
    print("CLEAN LEDGER REBUILD")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Remove existing ledger files
    removed = remove_ledger_files()
    if removed == 0:
        print("\n[INFO] No ledger files found to remove (or all were locked).")
        response = input("Continue with rebuild? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    # Step 2: Rebuild base ledger
    if not rebuild_base_ledger():
        print("\n[ERROR] Failed to rebuild base ledger. Stopping.")
        return
    
    # Step 3: Add CDs
    if not add_cds():
        print("\n[WARNING] Failed to add CD balances. Continuing...")
    
    # Step 4: Add HELOC
    if not add_heloc():
        print("\n[WARNING] Failed to add HELOC transactions. Continuing...")
    
    # Step 5: Add Mortgage
    if not add_mortgage():
        print("\n[WARNING] Failed to add mortgage balance. Continuing...")
    
    # Step 6: Show summary
    show_summary()
    
    print("\n" + "="*70)
    print(f"REBUILD COMPLETE")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[ABORTED] Rebuild interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FATAL ERROR] Rebuild failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

