"""Analyze assets from the ledger.

Includes:
- Cash balances (checking, savings)
- CDs (Certificates of Deposit)
- Investments (future: brokerage, retirement accounts)
- Real estate equity (future: home value - mortgage - HELOC)
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional


def get_archive_root():
    """Get the archive root directory."""
    import os
    archive_root = Path.home() / "Documents" / "finance_archive"
    
    if "FINANCE_ARCHIVE_ROOT" in os.environ:
        archive_root = Path(os.environ["FINANCE_ARCHIVE_ROOT"])
    
    return archive_root


def get_ledger_path():
    """Get the path to the ledger CSV file.
    
    Defaults to ledger_with_mortgage.csv (if available), then ledger_with_heloc.csv,
    then ledger_with_cds.csv, then ledger_reconciled.csv, then ledger.csv.
    """
    archive_root = get_archive_root()
    ledger_dir = archive_root / "20_ledger"
    
    # Prefer most complete ledger (with mortgage, HELOC, and CDs)
    paths = [
        ledger_dir / "ledger_with_mortgage.csv",  # Most complete (includes mortgage)
        ledger_dir / "ledger_with_heloc.csv",     # Has HELOC + CDs
        ledger_dir / "ledger_with_cds.csv",       # Has CDs
        ledger_dir / "ledger_reconciled.csv",     # Base reconciled ledger
        ledger_dir / "ledger.csv"                 # Original ledger
    ]
    
    for path in paths:
        if path.exists():
            return path
    
    return paths[3]  # Return default path even if doesn't exist (will error with helpful message)


def calculate_account_balances(ledger_df: pd.DataFrame, as_of_date: datetime = None) -> pd.DataFrame:
    """Calculate account balances from ledger entries.
    
    Args:
        ledger_df: DataFrame with ledger entries
        as_of_date: Calculate balances as of this date (default: latest date)
        
    Returns:
        DataFrame with account balances
    """
    # Filter by date if provided
    ledger_df['date'] = pd.to_datetime(ledger_df['date'])
    if as_of_date:
        ledger_df = ledger_df[ledger_df['date'] <= pd.to_datetime(as_of_date)].copy()
    
    # Group by account and sum amounts
    balances = ledger_df.groupby('account')['amount'].sum().reset_index()
    balances.columns = ['account', 'balance']
    
    # Sort by balance (descending)
    balances = balances.sort_values('balance', ascending=False)
    
    return balances


def analyze_cash_assets(ledger_df: pd.DataFrame) -> Dict:
    """Analyze cash assets (checking, savings).
    
    Note: Cash balances are currently placeholders ($0.00) because the ledger
    tracks transaction flows but lacks opening balances. The ledger sums all
    transactions from the start date, but without an opening balance entry,
    the calculated balance doesn't reflect actual account balances.
    
    TODO: Add opening balance entries or current balance snapshots to properly
    track cash assets. See BACKLOG.md for details.
    
    Returns:
        Dictionary with cash asset summary
    """
    # Find cash accounts (checking, savings, but not CDs)
    cash_accounts = ledger_df[
        (ledger_df['account'].str.startswith('Assets:', na=False)) &
        (ledger_df['account'].str.contains('Checking|Savings', case=False, na=False)) &
        (~ledger_df['account'].str.contains('CD', case=False, na=False))
    ].copy()
    
    # Exclude actual balances - use placeholders instead
    # The ledger tracks transaction flows but lacks opening balances,
    # so calculated balances are incorrect (would show -$155K instead of actual ~$1,800)
    # TODO: Add opening balance entries or current balance snapshots (see BACKLOG.md)
    
    # Get unique cash accounts from ledger
    existing_accounts = cash_accounts['account'].unique()
    
    # Create placeholder entries for each existing account
    if len(existing_accounts) == 0:
        return {
            'accounts': pd.DataFrame(columns=['account', 'balance']),
            'total': 0,
            'count': 0
        }
    
    cash_balances = pd.DataFrame([
        {'account': account, 'balance': 0.00}
        for account in existing_accounts
    ])
    
    total_cash = 0.00  # Placeholder total
    
    return {
        'accounts': cash_balances,
        'total': total_cash,
        'count': len(cash_balances)
    }


def analyze_cd_assets(ledger_df: pd.DataFrame) -> Dict:
    """Analyze CD (Certificate of Deposit) assets.
    
    Returns:
        Dictionary with CD asset summary
    """
    # Find CD accounts
    cd_accounts = ledger_df[
        ledger_df['account'].str.contains('CD:', case=False, na=False)
    ].copy()
    
    if len(cd_accounts) == 0:
        return {
            'accounts': pd.DataFrame(columns=['account', 'balance']),
            'total': 0,
            'count': 0
        }
    
    cd_balances = calculate_account_balances(cd_accounts)
    
    # Extract CD ID from account name for display
    cd_balances['cd_id'] = cd_balances['account'].str.extract(r'CD:(\d{4})', expand=False)
    
    total_cds = cd_balances['balance'].sum()
    
    return {
        'accounts': cd_balances,
        'total': total_cds,
        'count': len(cd_balances)
    }


def analyze_investment_assets(ledger_df: pd.DataFrame) -> Dict:
    """Analyze investment assets (brokerage, retirement accounts).
    
    Returns:
        Dictionary with investment asset summary
    """
    # Find investment accounts (future: 529, IRA, 401k, brokerage)
    investment_accounts = ledger_df[
        (ledger_df['account'].str.startswith('Assets:Investments:', na=False))
    ].copy()
    
    if len(investment_accounts) == 0:
        return {
            'accounts': pd.DataFrame(columns=['account', 'balance']),
            'total': 0,
            'count': 0
        }
    
    investment_balances = calculate_account_balances(investment_accounts)
    
    total_investments = investment_balances['balance'].sum()
    
    return {
        'accounts': investment_balances,
        'total': total_investments,
        'count': len(investment_balances)
    }


def analyze_liabilities(ledger_df: pd.DataFrame) -> Dict:
    """Analyze liabilities (mortgage, HELOC, loans).
    
    Excludes credit cards from the analysis.
    Excludes old payment aggregates for loans (Liabilities:Loans, Liabilities:StudentLoans)
    that incorrectly sum payments. These are kept as $0.00 placeholders until statement-based
    balances can be added (see BACKLOG.md).
    
    Returns:
        Dictionary with liability summary
    """
    # Find liability accounts
    liability_accounts = ledger_df[
        ledger_df['account'].str.startswith('Liabilities:', na=False)
    ].copy()
    
    # Exclude old mortgage payment transactions (Liabilities:Mortgage without institution)
    # Keep only statement-based balances (Liabilities:Mortgage:Institution)
    # This filters out payment transactions that incorrectly sum to a balance
    liability_accounts = liability_accounts[
        ~(liability_accounts['account'] == 'Liabilities:Mortgage')
    ].copy()
    
    # Exclude credit card accounts
    liability_accounts = liability_accounts[
        ~liability_accounts['account'].str.contains('CreditCards', case=False, na=False)
    ].copy()
    
    # Exclude old loan payment aggregates (Liabilities:Loans, Liabilities:StudentLoans)
    # These incorrectly sum payments instead of showing statement balances
    # Keep them as $0.00 placeholders until statement-based processing (see BACKLOG.md)
    loan_accounts_to_exclude = ['Liabilities:Loans', 'Liabilities:StudentLoans']
    liability_accounts = liability_accounts[
        ~liability_accounts['account'].isin(loan_accounts_to_exclude)
    ].copy()
    
    liability_balances = calculate_account_balances(liability_accounts)
    
    # Calculate total from actual balances (before adding placeholders)
    # For liability accounts in double-entry:
    # - Negative amounts = liability increases (you owe more) - e.g., advances
    # - Positive amounts = liability decreases (you pay down) - e.g., payments
    # So the sum is already negative if you owe money
    # Our entries are correctly signed (advances negative, payments positive)
    # So the balance is already negative and represents what you owe
    # We should NOT flip the sign - keep it negative to show what you owe
    # (Negative balance = you owe money, which is correct for liabilities)
    total_liabilities = liability_balances['balance'].sum()
    
    # Add placeholder entries for loan accounts with $0.00 balance
    # These will be populated when statement-based processing is implemented (see BACKLOG.md)
    placeholder_loans = pd.DataFrame([
        {'account': 'Liabilities:Loans', 'balance': 0.00},
        {'account': 'Liabilities:StudentLoans', 'balance': 0.00}
    ])
    
    # Combine actual balances with placeholders (for display only)
    # Note: Total liabilities calculated above excludes placeholders ($0.00 don't affect the total)
    liability_balances = pd.concat([liability_balances, placeholder_loans], ignore_index=True)
    
    return {
        'accounts': liability_balances,
        'total': total_liabilities,
        'count': len(liability_balances)
    }


def get_latest_home_value() -> Optional[float]:
    """Get the most recent home value from CSV.
    
    Returns:
        Latest home value, or None if not found
    """
    archive_root = get_archive_root()
    home_value_csv = archive_root / "10_normalized" / "real_estate" / "home_value.csv"
    
    if not home_value_csv.exists():
        return None
    
    try:
        df = pd.read_csv(home_value_csv)
        if len(df) == 0:
            return None
        
        # Parse date - handle different formats
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df[df['date'].notna()]  # Remove invalid dates
        df = df.sort_values('date', ascending=False)
        
        if len(df) == 0:
            return None
        
        # Parse value - handle commas
        value_str = str(df.iloc[0]['value']).replace(',', '').replace('$', '').strip()
        return float(value_str)
    except Exception as e:
        print(f"Warning: Could not load home value: {e}")
        return None


def analyze_real_estate(ledger_df: pd.DataFrame) -> Dict:
    """Analyze real estate (home value, mortgage, HELOC, equity).
    
    Equity = Home Value - Mortgage Balance - HELOC Balance
    
    Returns:
        Dictionary with real estate summary including equity
    """
    # Get home value from CSV
    home_value = get_latest_home_value()
    
    # Get mortgage balance from ledger
    mortgage_accounts = ledger_df[
        ledger_df['account'].str.contains('Liabilities:Mortgage:', case=False, na=False)
    ].copy()
    mortgage_balance = mortgage_accounts['amount'].sum() if len(mortgage_accounts) > 0 else 0
    
    # Get HELOC balance from ledger
    heloc_accounts = ledger_df[
        ledger_df['account'].str.contains('Liabilities:HELOC:', case=False, na=False)
    ].copy()
    heloc_balance = heloc_accounts['amount'].sum() if len(heloc_accounts) > 0 else 0
    
    # Calculate equity
    equity = None
    if home_value is not None:
        # Both mortgage and HELOC balances are negative (liabilities), so use abs()
        equity = home_value - abs(mortgage_balance) - abs(heloc_balance)
    
    return {
        'home_value': home_value,
        'mortgage_balance': abs(mortgage_balance) if mortgage_balance != 0 else None,
        'heloc_balance': abs(heloc_balance) if heloc_balance != 0 else None,
        'equity': equity,
        'has_data': home_value is not None or mortgage_balance != 0 or heloc_balance != 0
    }


def calculate_net_worth(cash_assets: Dict, cd_assets: Dict, investment_assets: Dict, 
                        liabilities: Dict, real_estate: Dict) -> Decimal:
    """Calculate net worth from all asset and liability categories."""
    total_assets = cash_assets['total'] + cd_assets['total'] + investment_assets['total']
    
    # Add real estate equity if available
    if real_estate.get('equity') is not None:
        total_assets += real_estate['equity']
    
    # Liabilities are stored as negative (what you owe), so we add them (subtract the absolute value)
    total_liabilities = abs(liabilities['total'])  # Convert to positive for net worth calculation
    net_worth = total_assets - total_liabilities
    return net_worth


def main():
    """Main analysis function."""
    ledger_path = get_ledger_path()
    
    print("="*80)
    print("ASSET ANALYSIS")
    print("="*80)
    print(f"Reading ledger from: {ledger_path}")
    
    if not ledger_path.exists():
        print(f"Error: Ledger file not found at {ledger_path}")
        return
    
    # Load ledger
    ledger_df = pd.read_csv(ledger_path)
    ledger_df['date'] = pd.to_datetime(ledger_df['date'])
    ledger_df['amount'] = pd.to_numeric(ledger_df['amount'], errors='coerce')
    
    print(f"Loaded {len(ledger_df)} ledger entries")
    
    # Analyze asset categories
    print("\n" + "="*80)
    print("CASH ASSETS (Checking & Savings)")
    print("="*80)
    cash = analyze_cash_assets(ledger_df)
    if cash['count'] > 0:
        print(f"\n{'Account':<50} {'Balance':>20}")
        print("-" * 70)
        for _, row in cash['accounts'].iterrows():
            print(f"{row['account']:<50} ${row['balance']:>19,.2f}")
        print("-" * 70)
        print(f"{'TOTAL CASH':<50} ${cash['total']:>19,.2f}")
    else:
        print("No cash accounts found.")
    
    print("\n" + "="*80)
    print("CD ASSETS (Certificates of Deposit)")
    print("="*80)
    cds = analyze_cd_assets(ledger_df)
    if cds['count'] > 0:
        print(f"\n{'CD ID':<10} {'Account':<40} {'Balance':>20}")
        print("-" * 70)
        for _, row in cds['accounts'].iterrows():
            cd_id = row.get('cd_id', 'N/A')
            print(f"{cd_id:<10} {row['account']:<40} ${row['balance']:>19,.2f}")
        print("-" * 70)
        print(f"{'TOTAL CDs':<50} ${cds['total']:>19,.2f}")
    else:
        print("No CD accounts found in ledger.")
        print("(Run add_cds_to_ledger.py to add CD balances)")
    
    print("\n" + "="*80)
    print("INVESTMENT ASSETS (Brokerage, Retirement)")
    print("="*80)
    investments = analyze_investment_assets(ledger_df)
    if investments['count'] > 0:
        print(f"\n{'Account':<50} {'Balance':>20}")
        print("-" * 70)
        for _, row in investments['accounts'].iterrows():
            print(f"{row['account']:<50} ${row['balance']:>19,.2f}")
        print("-" * 70)
        print(f"{'TOTAL INVESTMENTS':<50} ${investments['total']:>19,.2f}")
    else:
        print("No investment accounts found.")
    
    print("\n" + "="*80)
    print("REAL ESTATE ASSETS")
    print("="*80)
    real_estate = analyze_real_estate(ledger_df)
    if real_estate['has_data'] and real_estate.get('equity') is not None:
        print(f"\n{'Home Equity':<50} ${real_estate['equity']:>19,.2f}")
        print("  (Home Value - Mortgage - HELOC; mortgage and HELOC shown in Liabilities section)")
    else:
        print("No real estate data found.")
        print("(Add home value CSV and mortgage balance to enable equity calculation)")
    
    print("\n" + "="*80)
    print("LIABILITIES")
    print("="*80)
    liabilities = analyze_liabilities(ledger_df)
    if liabilities['count'] > 0:
        print(f"\n{'Account':<50} {'Balance':>20}")
        print("-" * 70)
        for _, row in liabilities['accounts'].iterrows():
            print(f"{row['account']:<50} ${row['balance']:>19,.2f}")
        print("-" * 70)
        print(f"{'TOTAL LIABILITIES':<50} ${liabilities['total']:>19,.2f}")
    else:
        print("No liabilities found.")
    
    # Calculate totals
    total_assets = cash['total'] + cds['total'] + investments['total']
    net_worth = calculate_net_worth(cash, cds, investments, liabilities, real_estate)
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"{'Cash Assets':<50} ${cash['total']:>19,.2f}")
    print(f"{'CD Assets':<50} ${cds['total']:>19,.2f}")
    print(f"{'Investment Assets':<50} ${investments['total']:>19,.2f}")
    if real_estate.get('equity') is not None:
        print(f"{'Home Equity':<50} ${real_estate['equity']:>19,.2f}")
    print("-" * 70)
    total_with_equity = total_assets + (real_estate.get('equity') or 0)
    print(f"{'Total Assets':<50} ${total_with_equity:>19,.2f}")
    print(f"{'Total Liabilities':<50} ${abs(liabilities['total']):>19,.2f}")
    print("=" * 70)
    print(f"{'NET WORTH':<50} ${net_worth:>19,.2f}")
    
    # Liquid vs Non-liquid breakdown
    print("\n" + "="*80)
    print("LIQUIDITY ANALYSIS")
    print("="*80)
    liquid_assets = cash['total']  # Cash is most liquid
    semi_liquid_assets = cds['total']  # CDs have maturity dates
    non_liquid_assets = investments['total']  # Investments may have restrictions
    
    print(f"{'Liquid Assets (Cash)':<50} ${liquid_assets:>19,.2f}")
    print(f"{'Semi-Liquid Assets (CDs)':<50} ${semi_liquid_assets:>19,.2f}")
    print(f"{'Non-Liquid Assets (Investments)':<50} ${non_liquid_assets:>19,.2f}")
    print("-" * 70)
    print(f"{'Total Liquid + Semi-Liquid':<50} ${liquid_assets + semi_liquid_assets:>19,.2f}")
    
    # Emergency fund analysis (user's goal: $100K in CDs)
    if cds['total'] > 0:
        emergency_fund_goal = 100000
        emergency_fund_coverage = (cds['total'] / emergency_fund_goal) * 100
        print(f"\n{'Emergency Fund (CDs)':<50} ${cds['total']:>19,.2f}")
        print(f"{'Goal ($100K)':<50} ${emergency_fund_goal:>19,.2f}")
        print(f"{'Coverage':<50} {emergency_fund_coverage:>18.1f}%")


if __name__ == "__main__":
    main()
