"""Analyze top income sources in detail."""

import pandas as pd
from pathlib import Path
from collections import Counter

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

def analyze_income_sources(ledger_path: Path):
    """Analyze top income sources in detail."""
    print(f"Reading ledger from: {ledger_path}")
    if 'reconciled' in str(ledger_path):
        print("(Using reconciled ledger with account matching corrections)")
    
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
    
    # Parse dates and amounts
    income_df['date'] = pd.to_datetime(income_df['date'])
    income_df['year'] = income_df['date'].dt.year
    income_df['amount'] = pd.to_numeric(income_df['amount'], errors='coerce')
    income_df['income_amount'] = -income_df['amount']  # Flip to positive
    income_df['category'] = income_df['account'].str.replace('Income:', '', regex=False)
    
    # Focus on top 3: Paychecks/Salary, Deposits, Unknown
    top_categories = ['Paychecks/Salary', 'Deposits', 'Unknown']
    
    for category in top_categories:
        cat_df = income_df[income_df['category'] == category].copy()
        
        if len(cat_df) == 0:
            continue
        
        print("\n" + "="*80)
        print(f"INCOME SOURCE: {category}")
        print("="*80)
        
        total = cat_df['income_amount'].sum()
        count = len(cat_df)
        avg = total / count if count > 0 else 0
        
        print(f"\nTotal: ${total:,.2f}")
        print(f"Transaction Count: {count:,}")
        print(f"Average per Transaction: ${avg:,.2f}")
        
        # Breakdown by year
        print(f"\n{'Year':<10} {'Total':>15} {'Count':>10} {'Avg':>15}")
        print("-" * 60)
        by_year = cat_df.groupby('year').agg({
            'income_amount': ['sum', 'count', 'mean']
        }).sort_index()
        for year in by_year.index:
            year_total = by_year.loc[year, ('income_amount', 'sum')]
            year_count = int(by_year.loc[year, ('income_amount', 'count')])
            year_avg = by_year.loc[year, ('income_amount', 'mean')]
            print(f"{year:<10} ${year_total:>14,.2f} {year_count:>10} ${year_avg:>14,.2f}")
        
        # Show sample transactions
        print(f"\nSample Transactions (first 20):")
        print(f"{'Date':<12} {'Description':<50} {'Amount':>15}")
        print("-" * 80)
        sample = cat_df.nlargest(20, 'income_amount')[['date', 'description', 'income_amount']]
        for _, row in sample.iterrows():
            date_str = row['date'].strftime('%Y-%m-%d') if pd.notna(row['date']) else 'N/A'
            desc = str(row['description'])[:48] if pd.notna(row['description']) else 'N/A'
            print(f"{date_str:<12} {desc:<50} ${row['income_amount']:>14,.2f}")
        
        # For Unknown category, show more analysis
        if category == 'Unknown':
            print(f"\n" + "="*80)
            print("UNKNOWN INCOME - DETAILED ANALYSIS")
            print("="*80)
            
            # Look at description patterns
            print(f"\nTop 20 Description Patterns (by count):")
            desc_counts = Counter(cat_df['description'].fillna('').astype(str))
            for desc, count in desc_counts.most_common(20):
                desc_short = desc[:60] if len(desc) > 60 else desc
                total_for_desc = cat_df[cat_df['description'] == desc]['income_amount'].sum()
                print(f"  {count:>5} transactions: {desc_short:<60} ${total_for_desc:>12,.2f}")
            
            # Look at amount distribution
            print(f"\nAmount Distribution:")
            print(f"  Min: ${cat_df['income_amount'].min():,.2f}")
            print(f"  Max: ${cat_df['income_amount'].max():,.2f}")
            print(f"  Median: ${cat_df['income_amount'].median():,.2f}")
            print(f"  Mean: ${cat_df['income_amount'].mean():,.2f}")
            
            # Look for very small amounts (might be misclassified)
            small_amounts = cat_df[cat_df['income_amount'] < 10]
            if len(small_amounts) > 0:
                print(f"\n  Small amounts (< $10): {len(small_amounts)} transactions, ${small_amounts['income_amount'].sum():,.2f} total")
            
            # Look for very large amounts
            large_amounts = cat_df[cat_df['income_amount'] > 1000]
            if len(large_amounts) > 0:
                print(f"\n  Large amounts (> $1,000): {len(large_amounts)} transactions, ${large_amounts['income_amount'].sum():,.2f} total")
                print(f"\n  Large amount transactions:")
                for _, row in large_amounts.nlargest(10, 'income_amount').iterrows():
                    date_str = row['date'].strftime('%Y-%m-%d') if pd.notna(row['date']) else 'N/A'
                    desc = str(row['description'])[:60] if pd.notna(row['description']) else 'N/A'
                    print(f"    {date_str} ${row['income_amount']:>12,.2f} - {desc}")

if __name__ == "__main__":
    ledger_path = get_ledger_path()
    analyze_income_sources(ledger_path)

