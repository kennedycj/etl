"""Add home value to the ledger for equity calculation.

This script manages home value entries, typically from property tax appraisals
or manual estimates. Home equity is calculated as:
Equity = Home Value - Mortgage Balance - HELOC Balance
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import pandas as pd

from finance_app.agents.data_curation.archive_scanner import get_archive_root


def get_archive_paths():
    """Get archive paths."""
    archive_root = get_archive_root()
    # Store home value CSV in a convenient location (could be in 00_raw or 10_normalized)
    home_value_dir = archive_root / "10_normalized" / "real_estate"
    home_value_dir.mkdir(parents=True, exist_ok=True)
    home_value_csv = home_value_dir / "home_value.csv"
    return archive_root, home_value_csv


def load_home_value_csv(csv_path: Path) -> pd.DataFrame:
    """Load home value data from CSV.
    
    Expected CSV format:
    - date: Valuation date (YYYY-MM-DD)
    - value: Home value (dollar amount)
    - source: Source of valuation (e.g., "Appraisal", "Property Tax", "Estimated")
    - notes: Optional notes
    
    Args:
        csv_path: Path to home value CSV
        
    Returns:
        DataFrame with home value data
    """
    if not csv_path.exists():
        return pd.DataFrame()
    
    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date', ascending=False)
    return df


def get_latest_home_value(csv_path: Path) -> Optional[float]:
    """Get the most recent home value from CSV.
    
    Args:
        csv_path: Path to home value CSV
        
    Returns:
        Latest home value, or None if not found
    """
    df = load_home_value_csv(csv_path)
    if len(df) == 0:
        return None
    
    return float(df.iloc[0]['value'])


def create_home_value_template(csv_path: Path):
    """Create a CSV template for home value entries."""
    template_data = {
        'date': [],
        'value': [],
        'source': [],
        'notes': []
    }
    
    template_df = pd.DataFrame(template_data)
    template_df.to_csv(csv_path, index=False)


def main():
    """Main function to manage home value data."""
    archive_root, home_value_csv = get_archive_paths()
    
    print("="*60)
    print("Home Value Management")
    print("="*60)
    
    # Load existing home values
    df = load_home_value_csv(home_value_csv)
    
    if len(df) == 0:
        print(f"\nNo home value data found.")
        print(f"Creating template at: {home_value_csv}")
        create_home_value_template(home_value_csv)
        print("\nPlease fill in the CSV with your home value data.")
        print("Required columns: date, value, source")
        print("  - date: Valuation date (YYYY-MM-DD)")
        print("  - value: Home value (dollar amount)")
        print("  - source: Source (e.g., 'Appraisal', 'Property Tax', 'Estimated')")
        print("  - notes: Optional notes")
        print("\nExample:")
        print("  date,value,source,notes")
        print("  2024-01-01,600000.00,Property Tax,Annual property tax assessment")
        print("  2025-01-01,620000.00,Appraisal,Annual appraisal")
        return
    
    # Show current home value data
    print(f"\nHome value history ({len(df)} entries):")
    print(df[['date', 'value', 'source', 'notes']].to_string(index=False))
    
    latest_value = get_latest_home_value(home_value_csv)
    latest_date = df.iloc[0]['date'].strftime('%Y-%m-%d')
    
    print(f"\nLatest home value: ${latest_value:,.2f} (as of {latest_date})")
    print(f"\n[OK] Home value data is ready for equity calculations")
    print(f"Location: {home_value_csv}")


if __name__ == "__main__":
    main()

