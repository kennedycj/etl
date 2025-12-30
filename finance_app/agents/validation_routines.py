"""Validation routines for comparing database values against external spreadsheets/reports."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from finance_app.database.models import AccountModel, TransactionModel
from finance_app.agents.analyzer import FinancialAnalyzer


class ValidationReport:
    """Validation report comparing database values to expected values."""
    
    def __init__(self, name: str):
        self.name = name
        self.checks = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def add_check(self, account_name: str, check_type: str, expected: float, actual: float, 
                  tolerance: float = 0.01, message: Optional[str] = None):
        """Add a validation check result."""
        diff = abs(expected - actual)
        passed = diff <= tolerance
        
        check = {
            "account": account_name,
            "type": check_type,
            "expected": expected,
            "actual": actual,
            "difference": diff,
            "tolerance": tolerance,
            "passed": passed,
            "message": message
        }
        
        self.checks.append(check)
        if passed:
            self.passed += 1
        else:
            if diff <= (tolerance * 10):  # Warning if close but not exact
                self.warnings += 1
            else:
                self.failed += 1
    
    def summary(self) -> Dict:
        """Get summary of validation results."""
        return {
            "name": self.name,
            "total_checks": len(self.checks),
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "passed_rate": (self.passed / len(self.checks) * 100) if self.checks else 0
        }


class ValidationRoutines:
    """Routines to validate database against external spreadsheets/reports."""
    
    def __init__(self, session: Session):
        self.session = session
        self.analyzer = FinancialAnalyzer(session)
    
    def validate_net_worth(self, expected_net_worth: float, as_of_date: Optional[datetime] = None, 
                          tolerance: float = 0.01) -> ValidationReport:
        """Validate net worth against expected value.
        
        Args:
            expected_net_worth: Expected net worth from spreadsheet
            as_of_date: Date to calculate net worth as of (default: now)
            tolerance: Acceptable difference in dollars
            
        Returns:
            ValidationReport with results
        """
        report = ValidationReport("Net Worth Validation")
        
        if as_of_date:
            # Calculate net worth as of specific date
            net_worth_data = self._calculate_net_worth_as_of(as_of_date)
        else:
            net_worth_data = self.analyzer.get_net_worth()
        
        actual_net_worth = net_worth_data["net_worth"]
        
        report.add_check(
            account_name="All Accounts",
            check_type="net_worth",
            expected=expected_net_worth,
            actual=actual_net_worth,
            tolerance=tolerance,
            message=f"Net worth: ${actual_net_worth:,.2f} (expected: ${expected_net_worth:,.2f})"
        )
        
        return report
    
    def validate_account_balance(self, account_name: str, expected_balance: float,
                                 as_of_date: Optional[datetime] = None, 
                                 tolerance: float = 0.01) -> ValidationReport:
        """Validate account balance against expected value (e.g., from statement).
        
        Args:
            account_name: Name of account to validate
            expected_balance: Expected balance from statement/spreadsheet
            as_of_date: Date to check balance as of (e.g., statement closing date)
            tolerance: Acceptable difference in dollars
            
        Returns:
            ValidationReport with results
        """
        report = ValidationReport(f"Account Balance Validation: {account_name}")
        
        account = self.session.query(AccountModel).filter(
            AccountModel.name == account_name
        ).first()
        
        if not account:
            report.add_check(
                account_name=account_name,
                check_type="account_exists",
                expected=1,
                actual=0,
                tolerance=0,
                message=f"Account '{account_name}' not found in database"
            )
            return report
        
        actual_balance = self.analyzer.get_account_balance(str(account.id), as_of_date)
        actual_balance_float = float(actual_balance) if actual_balance else 0.0
        
        report.add_check(
            account_name=account_name,
            check_type="account_balance",
            expected=expected_balance,
            actual=actual_balance_float,
            tolerance=tolerance,
            message=f"Balance as of {as_of_date.strftime('%Y-%m-%d') if as_of_date else 'now'}"
        )
        
        return report
    
    def validate_period_transaction_sum(self, account_name: str, start_date: datetime,
                                       end_date: datetime, expected_sum: float,
                                       tolerance: float = 0.01) -> ValidationReport:
        """Validate sum of transactions for a period (e.g., monthly statement totals).
        
        Args:
            account_name: Name of account
            start_date: Start of period
            end_date: End of period
            expected_sum: Expected sum from statement
            tolerance: Acceptable difference
            
        Returns:
            ValidationReport with results
        """
        report = ValidationReport(f"Period Transaction Sum: {account_name}")
        
        account = self.session.query(AccountModel).filter(
            AccountModel.name == account_name
        ).first()
        
        if not account:
            report.add_check(
                account_name=account_name,
                check_type="account_exists",
                expected=1,
                actual=0,
                tolerance=0,
                message=f"Account '{account_name}' not found"
            )
            return report
        
        result = self.session.query(func.sum(TransactionModel.amount)).filter(
            and_(
                TransactionModel.account_id == account.id,
                TransactionModel.transaction_date >= start_date,
                TransactionModel.transaction_date <= end_date
            )
        ).scalar()
        
        actual_sum = float(result) if result else 0.0
        
        report.add_check(
            account_name=account_name,
            check_type="period_transaction_sum",
            expected=expected_sum,
            actual=actual_sum,
            tolerance=tolerance,
            message=f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        )
        
        return report
    
    def validate_cash_flow(self, start_date: datetime, end_date: datetime,
                          expected_inflow: float, expected_outflow: float,
                          tolerance: float = 0.01) -> ValidationReport:
        """Validate cash flow (inflows and outflows) for a period.
        
        Args:
            start_date: Start of period
            end_date: End of period
            expected_inflow: Expected total inflows (positive amounts)
            expected_outflow: Expected total outflows (absolute value of negative amounts)
            tolerance: Acceptable difference
            
        Returns:
            ValidationReport with results
        """
        report = ValidationReport("Cash Flow Validation")
        
        # Calculate inflows (positive amounts)
        inflow_result = self.session.query(func.sum(TransactionModel.amount)).filter(
            and_(
                TransactionModel.transaction_date >= start_date,
                TransactionModel.transaction_date <= end_date,
                TransactionModel.amount > 0
            )
        ).scalar()
        actual_inflow = float(inflow_result) if inflow_result else 0.0
        
        # Calculate outflows (absolute value of negative amounts)
        outflow_result = self.session.query(func.sum(func.abs(TransactionModel.amount))).filter(
            and_(
                TransactionModel.transaction_date >= start_date,
                TransactionModel.transaction_date <= end_date,
                TransactionModel.amount < 0
            )
        ).scalar()
        actual_outflow = float(outflow_result) if outflow_result else 0.0
        
        report.add_check(
            account_name="All Accounts",
            check_type="cash_flow_inflow",
            expected=expected_inflow,
            actual=actual_inflow,
            tolerance=tolerance,
            message=f"Inflows: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        )
        
        report.add_check(
            account_name="All Accounts",
            check_type="cash_flow_outflow",
            expected=expected_outflow,
            actual=actual_outflow,
            tolerance=tolerance,
            message=f"Outflows: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        )
        
        return report
    
    def validate_transaction_count(self, account_name: str, start_date: datetime,
                                  end_date: datetime, expected_count: int,
                                  tolerance: int = 0) -> ValidationReport:
        """Validate number of transactions for a period (sanity check).
        
        Args:
            account_name: Name of account
            start_date: Start of period
            end_date: End of period
            expected_count: Expected number of transactions from statement
            tolerance: Acceptable difference in count
            
        Returns:
            ValidationReport with results
        """
        report = ValidationReport(f"Transaction Count: {account_name}")
        
        account = self.session.query(AccountModel).filter(
            AccountModel.name == account_name
        ).first()
        
        if not account:
            report.add_check(
                account_name=account_name,
                check_type="account_exists",
                expected=1,
                actual=0,
                tolerance=0,
                message=f"Account '{account_name}' not found"
            )
            return report
        
        actual_count = self.session.query(TransactionModel).filter(
            and_(
                TransactionModel.account_id == account.id,
                TransactionModel.transaction_date >= start_date,
                TransactionModel.transaction_date <= end_date
            )
        ).count()
        
        report.add_check(
            account_name=account_name,
            check_type="transaction_count",
            expected=float(expected_count),
            actual=float(actual_count),
            tolerance=float(tolerance),
            message=f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        )
        
        return report
    
    def check_period_coverage(self, account_name: str, expected_start: datetime,
                             expected_end: datetime) -> ValidationReport:
        """Check for gaps in transaction date coverage.
        
        Args:
            account_name: Name of account
            expected_start: Expected earliest transaction date
            expected_end: Expected latest transaction date
            
        Returns:
            ValidationReport with date coverage information
        """
        report = ValidationReport(f"Period Coverage: {account_name}")
        
        account = self.session.query(AccountModel).filter(
            AccountModel.name == account_name
        ).first()
        
        if not account:
            report.add_check(
                account_name=account_name,
                check_type="account_exists",
                expected=1,
                actual=0,
                tolerance=0,
                message=f"Account '{account_name}' not found"
            )
            return report
        
        # Get actual date range
        min_date_result = self.session.query(func.min(TransactionModel.transaction_date)).filter(
            TransactionModel.account_id == account.id
        ).scalar()
        max_date_result = self.session.query(func.max(TransactionModel.transaction_date)).filter(
            TransactionModel.account_id == account.id
        ).scalar()
        
        if min_date_result and max_date_result:
            actual_start = min_date_result
            actual_end = max_date_result
            
            # Check if coverage matches expected
            start_diff = abs((actual_start - expected_start).days)
            end_diff = abs((actual_end - expected_end).days)
            
            report.add_check(
                account_name=account_name,
                check_type="coverage_start",
                expected=0.0,
                actual=float(start_diff),
                tolerance=1.0,  # Allow 1 day difference
                message=f"Earliest transaction: {actual_start.strftime('%Y-%m-%d')} (expected: {expected_start.strftime('%Y-%m-%d')})"
            )
            
            report.add_check(
                account_name=account_name,
                check_type="coverage_end",
                expected=0.0,
                actual=float(end_diff),
                tolerance=1.0,
                message=f"Latest transaction: {actual_end.strftime('%Y-%m-%d')} (expected: {expected_end.strftime('%Y-%m-%d')})"
            )
        else:
            report.add_check(
                account_name=account_name,
                check_type="coverage",
                expected=1,
                actual=0,
                tolerance=0,
                message="No transactions found for account"
            )
        
        return report
    
    def validate_multiple_account_balances(self, balances: List[Tuple[str, float, Optional[datetime]]],
                                          tolerance: float = 0.01) -> ValidationReport:
        """Validate balances for multiple accounts at once.
        
        Args:
            balances: List of tuples (account_name, expected_balance, as_of_date)
            tolerance: Acceptable difference
            
        Returns:
            Combined ValidationReport
        """
        report = ValidationReport("Multiple Account Balance Validation")
        
        for account_name, expected_balance, as_of_date in balances:
            account_report = self.validate_account_balance(
                account_name, expected_balance, as_of_date, tolerance
            )
            report.checks.extend(account_report.checks)
            report.passed += account_report.passed
            report.failed += account_report.failed
            report.warnings += account_report.warnings
        
        return report
    
    def _calculate_net_worth_as_of(self, as_of_date: datetime) -> Dict:
        """Calculate net worth as of a specific date."""
        accounts = self.session.query(AccountModel).all()
        
        assets = Decimal('0.00')
        liabilities = Decimal('0.00')
        
        asset_types = ['checking', 'savings', 'cd', 'brokerage', 'ira_traditional', 
                      'ira_roth', 'ira_rollover', '401k', '529', 'able']
        liability_types = ['credit_card', 'heloc', 'mortgage']
        
        for account in accounts:
            balance = self.analyzer.get_account_balance(str(account.id), as_of_date)
            
            if account.account_type in asset_types:
                assets += balance or Decimal('0.00')
            elif account.account_type in liability_types:
                debt_amount = abs(balance) if balance and balance < 0 else Decimal('0.00')
                liabilities += debt_amount
        
        net_worth = assets - liabilities
        
        return {
            "assets": float(assets),
            "liabilities": float(liabilities),
            "net_worth": float(net_worth),
            "as_of_date": as_of_date.isoformat()
        }

