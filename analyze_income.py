"""Analyze income by year from the ledger."""

import pandas as pd
from pathlib import Path
from decimal import Decimal
from datetime import datetime

def get_ledger_path():
    """Get the path to the ledger CSV file."""
    archive_root = Path.home() / "Documents" / "finance_archive"
    ledger_path = archive_root / "20_ledger" / "ledger.csv"
    
    # Try environment variable first
    import os
    if "FINANCE_ARCHIVE_ROOT" in os.environ:
        archive_root = Path(os.environ["FINANCE_ARCHIVE_ROOT"])
        ledger_path = archive_root / "20_ledger" / "ledger.csv"
    
    return ledger_path

def analyze_income_by_year(ledger_path: Path):
    """Analyze income by year from the ledger CSV."""
    print(f"Reading ledger from: {ledger_path}")
    
    if not ledger_path.exists():
        print(f"Error: Ledger file not found at {ledger_path}")
        return
    
    # Read the ledger CSV
    df = pd.read_csv(ledger_path)
    
    # Filter for income accounts
    income_df = df[df['account'].str.startswith('Income:', na=False)].copy()
    
    if len(income_df) == 0:
        print("No income transactions found in ledger.")
        return
    
    # Parse dates
    income_df['date'] = pd.to_datetime(income_df['date'])
    income_df['year'] = income_df['date'].dt.year
    
    # Convert amount to numeric (should already be numeric, but ensure it)
    # In double-entry, income is negative (credit), so flip to positive for display
    income_df['amount'] = pd.to_numeric(income_df['amount'], errors='coerce')
    income_df['income_amount'] = -income_df['amount']  # Flip to positive for display
    
    # Group by year and sum (using positive amounts for display)
    income_by_year = income_df.groupby('year')['income_amount'].sum().sort_index()
    
    print("\n" + "="*60)
    print("INCOME BY YEAR")
    print("="*60)
    print(f"\n{'Year':<10} {'Total Income':>20} {'Transaction Count':>20}")
    print("-" * 60)
    
    total_all_years = 0
    for year, total in income_by_year.items():
        count = len(income_df[income_df['year'] == year])
        total_all_years += total
        print(f"{year:<10} ${total:>19,.2f} {count:>20}")
    
    print("-" * 60)
    print(f"{'TOTAL':<10} ${total_all_years:>19,.2f} {len(income_df):>20}")
    
    # Show breakdown by income category
    print("\n" + "="*60)
    print("INCOME BY CATEGORY (All Years)")
    print("="*60)
    
    # Extract category from account name (Income:Category)
    income_df['category'] = income_df['account'].str.replace('Income:', '', regex=False)
    income_by_category = income_df.groupby('category')['income_amount'].sum().sort_values(ascending=False)
    
    print(f"\n{'Category':<30} {'Total Income':>20} {'Count':>10}")
    print("-" * 60)
    for category, total in income_by_category.items():
        count = len(income_df[income_df['category'] == category])
        print(f"{category:<30} ${total:>19,.2f} {count:>10}")
    
    # Show monthly breakdown for most recent year
    if len(income_by_year) > 0:
        most_recent_year = income_by_year.index[-1]
        recent_year_df = income_df[income_df['year'] == most_recent_year].copy()
        recent_year_df['month'] = recent_year_df['date'].dt.month
        recent_year_df['month_name'] = recent_year_df['date'].dt.strftime('%B')
        
        income_by_month = recent_year_df.groupby(['month', 'month_name'])['income_amount'].sum().sort_index()
        
        print("\n" + "="*60)
        print(f"MONTHLY INCOME BREAKDOWN - {most_recent_year}")
        print("="*60)
        print(f"\n{'Month':<15} {'Total Income':>20} {'Transaction Count':>20}")
        print("-" * 60)
        
        for (month, month_name), total in income_by_month.items():
            count = len(recent_year_df[recent_year_df['month'] == month])
            print(f"{month_name:<15} ${total:>19,.2f} {count:>20}")
        
        year_total = income_by_year[most_recent_year]
        print("-" * 60)
        print(f"{'TOTAL':<15} ${year_total:>19,.2f} {len(recent_year_df):>20}")

if __name__ == "__main__":
    ledger_path = get_ledger_path()
    analyze_income_by_year(ledger_path)

