"""Financial data analysis agent - queries and insights."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from finance_app.database.models import AccountModel, TransactionModel


class FinancialAnalyzer:
    """Agent that analyzes financial data and provides insights."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_account_summary(self) -> Dict:
        """Get summary of all accounts."""
        accounts = self.session.query(AccountModel).all()
        
        summary = {
            "total_accounts": len(accounts),
            "by_type": {},
            "accounts": []
        }
        
        for account in accounts:
            balance = self.get_account_balance(account.id)
            account_data = {
                "id": str(account.id),
                "name": account.name,
                "type": account.account_type,
                "institution": account.institution_name,
                "balance": float(balance) if balance else 0.0,
                "is_closed": account.close_date is not None
            }
            summary["accounts"].append(account_data)
            
            # Count by type
            acc_type = account.account_type
            if acc_type not in summary["by_type"]:
                summary["by_type"][acc_type] = 0
            summary["by_type"][acc_type] += 1
        
        return summary
    
    def get_account_balance(self, account_id: str, as_of_date: Optional[datetime] = None) -> Optional[Decimal]:
        """Get account balance by summing transactions.
        
        For asset accounts: positive balance = money you have
        For liability accounts: negative balance = debt you owe (positive = credit)
        """
        account = self.session.query(AccountModel).filter(AccountModel.id == account_id).first()
        if not account:
            return Decimal('0.00')
        
        query = self.session.query(func.sum(TransactionModel.amount)).filter(
            TransactionModel.account_id == account_id
        )
        
        if as_of_date:
            query = query.filter(TransactionModel.transaction_date <= as_of_date)
        
        result = query.scalar()
        balance = result if result is not None else Decimal('0.00')
        
        # For liability accounts (credit cards, loans), negative balance = debt
        # For assets, positive balance = money you have
        # Return as-is - the net worth calculation handles the signs
        return balance
    
    def get_net_worth(self) -> Dict:
        """Calculate net worth (assets - liabilities)."""
        accounts = self.session.query(AccountModel).all()
        
        assets = Decimal('0.00')
        liabilities = Decimal('0.00')
        
        asset_types = ['checking', 'savings', 'cd', 'brokerage', 'ira_traditional', 
                      'ira_roth', 'ira_rollover', '401k', '529', 'able']
        liability_types = ['credit_card', 'heloc', 'mortgage']
        
        for account in accounts:
            balance = self.get_account_balance(account.id)
            
            if account.account_type in asset_types:
                # Assets: positive balance = money you have
                assets += balance or Decimal('0.00')
            elif account.account_type in liability_types:
                # Liabilities: negative balance = debt, so we need absolute value for net worth
                # If balance is negative, that's debt (subtract it from net worth)
                # If balance is positive, that's credit/overpayment (still subtract but it's a reduction)
                debt_amount = abs(balance) if balance < 0 else Decimal('0.00')
                liabilities += debt_amount
        
        net_worth = assets - liabilities
        
        return {
            "assets": float(assets),
            "liabilities": float(liabilities),
            "net_worth": float(net_worth),
            "calculated_at": datetime.utcnow().isoformat()
        }
    
    def get_spending_by_category(self, start_date: Optional[datetime] = None, 
                                 end_date: Optional[datetime] = None) -> Dict:
        """Analyze spending by category."""
        query = self.session.query(
            TransactionModel.category,
            func.sum(TransactionModel.amount).label('total'),
            func.count(TransactionModel.id).label('count')
        ).filter(
            TransactionModel.amount < 0  # Only expenses (negative amounts)
        )
        
        if start_date:
            query = query.filter(TransactionModel.transaction_date >= start_date)
        if end_date:
            query = query.filter(TransactionModel.transaction_date <= end_date)
        
        results = query.group_by(TransactionModel.category).order_by(
            func.sum(TransactionModel.amount)
        ).all()
        
        spending = {}
        for category, total, count in results:
            if category:  # Skip null categories
                spending[category] = {
                    "total": float(total),
                    "count": count,
                    "average": float(total / count) if count > 0 else 0.0
                }
        
        return spending
    
    def get_monthly_trends(self, months: int = 12) -> List[Dict]:
        """Get monthly income and expense trends."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months * 30)
        
        # Group by month
        query = self.session.query(
            func.date_trunc('month', TransactionModel.transaction_date).label('month'),
            func.sum(
                func.case(
                    (TransactionModel.amount > 0, TransactionModel.amount),
                    else_=0
                )
            ).label('income'),
            func.sum(
                func.case(
                    (TransactionModel.amount < 0, func.abs(TransactionModel.amount)),
                    else_=0
                )
            ).label('expenses')
        ).filter(
            TransactionModel.transaction_date >= start_date
        ).group_by('month').order_by('month')
        
        results = query.all()
        
        trends = []
        for month, income, expenses in results:
            trends.append({
                "month": month.strftime('%Y-%m') if month else None,
                "income": float(income) if income else 0.0,
                "expenses": float(expenses) if expenses else 0.0,
                "net": float(income - expenses) if income and expenses else 0.0
            })
        
        return trends
    
    def identify_anomalies(self) -> List[Dict]:
        """Identify unusual transactions that might need review."""
        anomalies = []
        
        # Large transactions (more than 2 standard deviations from mean)
        stats = self.session.query(
            func.avg(func.abs(TransactionModel.amount)).label('avg'),
            func.stddev(func.abs(TransactionModel.amount)).label('stddev')
        ).scalar_one()
        
        if stats and stats[1]:  # If we have stddev
            avg_amt = float(stats[0])
            stddev_amt = float(stats[1])
            threshold = avg_amt + (2 * stddev_amt)
            
            large_txns = self.session.query(TransactionModel).filter(
                func.abs(TransactionModel.amount) > threshold
            ).order_by(func.abs(TransactionModel.amount).desc()).limit(10).all()
            
            for txn in large_txns:
                anomalies.append({
                    "type": "large_transaction",
                    "transaction_id": str(txn.id),
                    "date": txn.transaction_date.isoformat() if txn.transaction_date else None,
                    "amount": float(txn.amount),
                    "description": txn.description,
                    "account_id": str(txn.account_id)
                })
        
        return anomalies
    
    def get_unreconciled_transactions(self) -> Dict:
        """Find transactions that need reconciliation."""
        unreconciled = self.session.query(TransactionModel).filter(
            TransactionModel.reconcile_status == 'unreconciled'
        ).count()
        
        pending = self.session.query(TransactionModel).filter(
            TransactionModel.status == 'pending'
        ).count()
        
        return {
            "unreconciled_count": unreconciled,
            "pending_count": pending,
            "needs_attention": unreconciled + pending
        }

