"""Run validation routines against database and print results."""

import os
import sys
from datetime import datetime
from decimal import Decimal

from finance_app.database.connection import create_database_engine, get_session
from finance_app.agents.validation_routines import ValidationRoutines


def print_validation_report(report):
    """Print a formatted validation report."""
    summary = report.summary()
    
    print(f"\n{'='*70}")
    print(f"VALIDATION: {summary['name']}")
    print(f"{'='*70}")
    print(f"Total Checks: {summary['total_checks']}")
    print(f"✓ Passed: {summary['passed']}")
    print(f"✗ Failed: {summary['failed']}")
    print(f"⚠  Warnings: {summary['warnings']}")
    print(f"Pass Rate: {summary['passed_rate']:.1f}%")
    
    print(f"\n{'Details:':<20} {'Expected':<15} {'Actual':<15} {'Diff':<15} {'Status':<10}")
    print("-" * 70)
    
    for check in report.checks:
        status = "✓ PASS" if check['passed'] else ("⚠ WARN" if abs(check['difference']) <= (check['tolerance'] * 10) else "✗ FAIL")
        
        if check['type'] in ['net_worth', 'account_balance', 'period_transaction_sum', 'cash_flow_inflow', 'cash_flow_outflow']:
            expected_str = f"${check['expected']:,.2f}"
            actual_str = f"${check['actual']:,.2f}"
            diff_str = f"${check['difference']:,.2f}"
        else:
            expected_str = f"{check['expected']:.0f}"
            actual_str = f"{check['actual']:.0f}"
            diff_str = f"{check['difference']:.0f}"
        
        detail = f"{check['account']} ({check['type']})"
        print(f"{detail:<20} {expected_str:<15} {actual_str:<15} {diff_str:<15} {status:<10}")
        
        if check.get('message'):
            print(f"  → {check['message']}")


def example_net_worth_validation(session, expected_net_worth: float):
    """Example: Validate net worth."""
    validator = ValidationRoutines(session)
    report = validator.validate_net_worth(expected_net_worth)
    print_validation_report(report)


def example_account_balance_validation(session, account_name: str, expected_balance: float, 
                                      as_of_date: datetime = None):
    """Example: Validate account balance."""
    validator = ValidationRoutines(session)
    report = validator.validate_account_balance(account_name, expected_balance, as_of_date)
    print_validation_report(report)


def example_period_validation(session, account_name: str, start_date: datetime, end_date: datetime,
                             expected_balance: float, expected_transaction_sum: float = None,
                             expected_transaction_count: int = None):
    """Example: Validate account for a period (balance, transaction sum, count)."""
    validator = ValidationRoutines(session)
    
    # Validate closing balance
    balance_report = validator.validate_account_balance(account_name, expected_balance, end_date)
    print_validation_report(balance_report)
    
    # Validate transaction sum if provided
    if expected_transaction_sum is not None:
        sum_report = validator.validate_period_transaction_sum(
            account_name, start_date, end_date, expected_transaction_sum
        )
        print_validation_report(sum_report)
    
    # Validate transaction count if provided
    if expected_transaction_count is not None:
        count_report = validator.validate_transaction_count(
            account_name, start_date, end_date, expected_transaction_count
        )
        print_validation_report(count_report)


def example_cash_flow_validation(session, start_date: datetime, end_date: datetime,
                                 expected_inflow: float, expected_outflow: float):
    """Example: Validate cash flow for a period."""
    validator = ValidationRoutines(session)
    report = validator.validate_cash_flow(start_date, end_date, expected_inflow, expected_outflow)
    print_validation_report(report)


def example_multi_account_validation(session, balances: list):
    """Example: Validate multiple account balances at once.
    
    Args:
        balances: List of tuples (account_name, expected_balance, as_of_date)
                  as_of_date can be None for current balance
    """
    validator = ValidationRoutines(session)
    report = validator.validate_multiple_account_balances(balances)
    print_validation_report(report)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_validations.py <database_url>")
        print("\nExample validations:")
        print("  # Validate net worth")
        print("  python -c \"from run_validations import *; session=get_session(create_database_engine('postgresql://...')); example_net_worth_validation(session, 500000.00)\"")
        print("\n  # Validate account balance")
        print("  python -c \"from run_validations import *; from datetime import datetime; session=get_session(create_database_engine('postgresql://...')); example_account_balance_validation(session, 'Account Name', 1234.56, datetime(2025, 12, 31))\"")
        print("\nOr set DATABASE_URL environment variable and import/use the functions in your own script")
        sys.exit(1)
    
    database_url = sys.argv[1]
    engine = create_database_engine(database_url)
    session = get_session(engine)
    
    try:
        print("Validation routines available:")
        print("  - validate_net_worth(expected_net_worth, as_of_date=None)")
        print("  - validate_account_balance(account_name, expected_balance, as_of_date=None)")
        print("  - validate_period_transaction_sum(account_name, start_date, end_date, expected_sum)")
        print("  - validate_cash_flow(start_date, end_date, expected_inflow, expected_outflow)")
        print("  - validate_transaction_count(account_name, start_date, end_date, expected_count)")
        print("  - validate_multiple_account_balances(balances_list)")
        print("\nImport ValidationRoutines to use these functions programmatically.")
        print("Or use the example_* functions in this file.")
        
    finally:
        session.close()

