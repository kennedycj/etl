"""Analyze expenses by year from the ledger."""

import pandas as pd
from pathlib import Path
from decimal import Decimal
from datetime import datetime

def get_ledger_path():
    """Get the path to the ledger CSV file.
    
    Defaults to ledger_reconciled.csv (with account matching corrections).
    Falls back to ledger.csv if reconciled version doesn't exist.
    """
    import os
    archive_root = Path.home() / "Documents" / "finance_archive"
    
    if "FINANCE_ARCHIVE_ROOT" in os.environ:
        archive_root = Path(os.environ["FINANCE_ARCHIVE_ROOT"])
    
    # Prefer reconciled ledger (with corrections), fall back to original
    reconciled_path = archive_root / "20_ledger" / "ledger_reconciled.csv"
    original_path = archive_root / "20_ledger" / "ledger.csv"
    
    if reconciled_path.exists():
        return reconciled_path
    elif original_path.exists():
        return original_path
    else:
        return original_path  # Return path even if doesn't exist (will error with helpful message)

def analyze_expenses_by_year(ledger_path: Path):
    """Analyze expenses by year from the ledger CSV."""
    print(f"Reading ledger from: {ledger_path}")
    if 'reconciled' in str(ledger_path):
        print("(Using reconciled ledger with account matching corrections)")
    
    if not ledger_path.exists():
        print(f"Error: Ledger file not found at {ledger_path}")
        return
    
    # Read the ledger CSV
    df = pd.read_csv(ledger_path)
    
    # Filter for expense accounts
    expense_df = df[df['account'].str.startswith('Expenses:', na=False)].copy()
    
    if len(expense_df) == 0:
        print("No expense transactions found in ledger.")
        return
    
    # Parse dates
    expense_df['date'] = pd.to_datetime(expense_df['date'])
    expense_df['year'] = expense_df['date'].dt.year
    
    # Convert amount to numeric
    # In double-entry, expenses are positive (debit), so use as-is for display
    expense_df['amount'] = pd.to_numeric(expense_df['amount'], errors='coerce')
    expense_df['expense_amount'] = expense_df['amount']  # Already positive
    
    # Group by year and sum
    expenses_by_year = expense_df.groupby('year')['expense_amount'].sum().sort_index()
    
    print("\n" + "="*60)
    print("EXPENSES BY YEAR")
    print("="*60)
    print(f"\n{'Year':<10} {'Total Expenses':>20} {'Transaction Count':>20}")
    print("-" * 60)
    
    total_all_years = 0
    for year, total in expenses_by_year.items():
        count = len(expense_df[expense_df['year'] == year])
        total_all_years += total
        print(f"{year:<10} ${total:>19,.2f} {count:>20}")
    
    print("-" * 60)
    print(f"{'TOTAL':<10} ${total_all_years:>19,.2f} {len(expense_df):>20}")
    
    # Show breakdown by expense category
    print("\n" + "="*60)
    print("EXPENSES BY CATEGORY (All Years)")
    print("="*60)
    
    # Extract category from account name (Expenses:Category)
    expense_df['category'] = expense_df['account'].str.replace('Expenses:', '', regex=False)
    expenses_by_category = expense_df.groupby('category')['expense_amount'].sum().sort_values(ascending=False)
    
    print(f"\n{'Category':<30} {'Total Expenses':>20} {'Count':>10}")
    print("-" * 60)
    for category, total in expenses_by_category.items():
        count = len(expense_df[expense_df['category'] == category])
        print(f"{category:<30} ${total:>19,.2f} {count:>10}")
    
    # Show top 20 categories
    print("\n" + "="*60)
    print("TOP 20 EXPENSE CATEGORIES")
    print("="*60)
    print(f"\n{'Category':<30} {'Total Expenses':>20} {'Count':>10}")
    print("-" * 60)
    for category, total in expenses_by_category.head(20).items():
        count = len(expense_df[expense_df['category'] == category])
        print(f"{category:<30} ${total:>19,.2f} {count:>10}")
    
    # Show monthly breakdown for most recent year
    if len(expenses_by_year) > 0:
        most_recent_year = expenses_by_year.index[-1]
        recent_year_df = expense_df[expense_df['year'] == most_recent_year].copy()
        recent_year_df['month'] = recent_year_df['date'].dt.month
        recent_year_df['month_name'] = recent_year_df['date'].dt.strftime('%B')
        
        expenses_by_month = recent_year_df.groupby(['month', 'month_name'])['expense_amount'].sum().sort_index()
        
        print("\n" + "="*60)
        print(f"MONTHLY EXPENSES BREAKDOWN - {most_recent_year}")
        print("="*60)
        print(f"\n{'Month':<15} {'Total Expenses':>20} {'Transaction Count':>20}")
        print("-" * 60)
        
        for (month, month_name), total in expenses_by_month.items():
            count = len(recent_year_df[recent_year_df['month'] == month])
            print(f"{month_name:<15} ${total:>19,.2f} {count:>20}")
        
        year_total = expenses_by_year[most_recent_year]
        print("-" * 60)
        print(f"{'TOTAL':<15} ${year_total:>19,.2f} {len(recent_year_df):>20}")
    
    # Calculate savings rate (if we have income data)
    print("\n" + "="*60)
    print("SAVINGS ANALYSIS")
    print("="*60)
    
    # Get income data for comparison
    income_df = df[df['account'].str.startswith('Income:', na=False)].copy()
    if len(income_df) > 0:
        income_df['date'] = pd.to_datetime(income_df['date'])
        income_df['year'] = income_df['date'].dt.year
        income_df['amount'] = pd.to_numeric(income_df['amount'], errors='coerce')
        income_df['income_amount'] = -income_df['amount']  # Flip to positive
        
        income_by_year = income_df.groupby('year')['income_amount'].sum().sort_index()
        
        print(f"\n{'Year':<10} {'Income':>15} {'Expenses':>15} {'Savings':>15} {'Savings %':>10}")
        print("-" * 60)
        
        for year in sorted(set(expenses_by_year.index) | set(income_by_year.index)):
            income = income_by_year.get(year, 0)
            expenses = expenses_by_year.get(year, 0)
            savings = income - expenses
            savings_pct = (savings / income * 100) if income > 0 else 0
            print(f"{year:<10} ${income:>14,.2f} ${expenses:>14,.2f} ${savings:>14,.2f} {savings_pct:>9.1f}%")

if __name__ == "__main__":
    ledger_path = get_ledger_path()
    analyze_expenses_by_year(ledger_path)

