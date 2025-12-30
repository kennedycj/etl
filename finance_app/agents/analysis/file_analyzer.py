"""Analyze processed transaction files directly (no database required)."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from finance_app.agents.data_curation.archive_scanner import get_archive_root


class FileAnalyzer:
    """Analyze financial data from processed CSV files without database."""
    
    def __init__(self, archive_root: Optional[Path] = None):
        """Initialize analyzer.
        
        Args:
            archive_root: Archive root directory (uses default if None)
        """
        if archive_root is None:
            archive_root = get_archive_root()
        self.archive_root = Path(archive_root)
        self.processed_path = self.archive_root / "01_processed"
        self.transactions_df: Optional[pd.DataFrame] = None
    
    def load_all_transactions(self) -> pd.DataFrame:
        """Load all processed transaction files.
        
        Returns:
            Combined DataFrame of all transactions
        """
        if self.transactions_df is not None:
            return self.transactions_df
        
        all_transactions = []
        
        if not self.processed_path.exists():
            return pd.DataFrame()
        
        # Find all cleansed CSV files
        for csv_file in self.processed_path.rglob("cleansed_*.csv"):
            try:
                df = pd.read_csv(csv_file)
                df['_source_file'] = str(csv_file.relative_to(self.processed_path))
                all_transactions.append(df)
            except Exception as e:
                print(f"Warning: Could not read {csv_file}: {e}")
                continue
        
        if not all_transactions:
            self.transactions_df = pd.DataFrame()
            return self.transactions_df
        
        combined = pd.concat(all_transactions, ignore_index=True)
        
        # Parse dates and amounts
        for col in combined.columns:
            if '_parsed_date' in col or 'date' in col.lower():
                try:
                    combined[col] = pd.to_datetime(combined[col], errors='coerce')
                except:
                    pass
            if '_parsed_amount' in col or 'amount' in col.lower():
                try:
                    combined[col] = pd.to_numeric(combined[col], errors='coerce')
                except:
                    pass
        
        self.transactions_df = combined
        return combined
    
    def get_net_worth_by_date(self, as_of_date: Optional[datetime] = None) -> Dict:
        """Calculate net worth from transactions.
        
        Args:
            as_of_date: Calculate as of this date (default: latest transaction)
            
        Returns:
            Dictionary with assets, liabilities, net_worth
        """
        df = self.load_all_transactions()
        
        if df.empty:
            return {'assets': 0.0, 'liabilities': 0.0, 'net_worth': 0.0}
        
        # This is simplified - real implementation needs account types
        # For now, sum all amounts as assets (needs proper account classification)
        
        date_col = None
        for col in ['_parsed_date', 'Date', 'date']:
            if col in df.columns:
                date_col = col
                break
        
        amount_col = None
        for col in ['_parsed_amount', 'Amount', 'amount']:
            if col in df.columns:
                amount_col = col
                break
        
        if not date_col or not amount_col:
            return {'assets': 0.0, 'liabilities': 0.0, 'net_worth': 0.0}
        
        # Filter by date if provided
        if as_of_date:
            df_filtered = df[df[date_col] <= as_of_date]
        else:
            df_filtered = df
        
        # Sum amounts (simplified - needs account type classification)
        total = float(df_filtered[amount_col].sum())
        
        return {
            'assets': total if total > 0 else 0.0,
            'liabilities': abs(total) if total < 0 else 0.0,
            'net_worth': total
        }
    
    def get_cash_flow(self, start_date: datetime, end_date: datetime) -> Dict:
        """Calculate cash flow for a period.
        
        Args:
            start_date: Start of period
            end_date: End of period
            
        Returns:
            Dictionary with inflow, outflow, net
        """
        df = self.load_all_transactions()
        
        if df.empty:
            return {'inflow': 0.0, 'outflow': 0.0, 'net': 0.0}
        
        date_col = None
        for col in ['_parsed_date', 'Date', 'date']:
            if col in df.columns:
                date_col = col
                break
        
        amount_col = None
        for col in ['_parsed_amount', 'Amount', 'amount']:
            if col in df.columns:
                amount_col = col
                break
        
        if not date_col or not amount_col:
            return {'inflow': 0.0, 'outflow': 0.0, 'net': 0.0}
        
        # Filter by date range
        df_filtered = df[(df[date_col] >= start_date) & (df[date_col] <= end_date)]
        
        # Calculate inflows (positive) and outflows (negative)
        inflows = df_filtered[df_filtered[amount_col] > 0][amount_col].sum()
        outflows = abs(df_filtered[df_filtered[amount_col] < 0][amount_col].sum())
        
        return {
            'inflow': float(inflows),
            'outflow': float(outflows),
            'net': float(inflows - outflows)
        }
    
    def get_spending_by_period(self, period: str = 'month') -> pd.DataFrame:
        """Get spending summary by period.
        
        Args:
            period: 'month', 'quarter', or 'year'
            
        Returns:
            DataFrame with period, total_spending, transaction_count
        """
        df = self.load_all_transactions()
        
        if df.empty:
            return pd.DataFrame()
        
        date_col = None
        for col in ['_parsed_date', 'Date', 'date']:
            if col in df.columns:
                date_col = col
                break
        
        amount_col = None
        for col in ['_parsed_amount', 'Amount', 'amount']:
            if col in df.columns:
                amount_col = col
                break
        
        if not date_col or not amount_col:
            return pd.DataFrame()
        
        # Filter to expenses only (negative amounts)
        expenses = df[df[amount_col] < 0].copy()
        
        # Group by period
        if period == 'month':
            expenses['period'] = expenses[date_col].dt.to_period('M')
        elif period == 'quarter':
            expenses['period'] = expenses[date_col].dt.to_period('Q')
        elif period == 'year':
            expenses['period'] = expenses[date_col].dt.to_period('Y')
        else:
            return pd.DataFrame()
        
        summary = expenses.groupby('period').agg({
            amount_col: ['sum', 'count']
        }).reset_index()
        
        summary.columns = ['period', 'total_spending', 'transaction_count']
        summary['total_spending'] = abs(summary['total_spending'])  # Make positive
        
        return summary


if __name__ == "__main__":
    analyzer = FileAnalyzer()
    
    print("Loading transactions...")
    df = analyzer.load_all_transactions()
    print(f"Loaded {len(df)} transactions")
    
    if not df.empty:
        print("\nCash Flow (Last 30 days):")
        from datetime import timedelta
        end = datetime.now()
        start = end - timedelta(days=30)
        cash_flow = analyzer.get_cash_flow(start, end)
        print(f"  Inflow: ${cash_flow['inflow']:,.2f}")
        print(f"  Outflow: ${cash_flow['outflow']:,.2f}")
        print(f"  Net: ${cash_flow['net']:,.2f}")

