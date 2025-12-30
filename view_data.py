"""Simple script to view data in the database."""

import sys
from datetime import datetime
from decimal import Decimal

try:
    from tabulate import tabulate
except ImportError:
    print("Error: tabulate not installed. Install with: pip install -e '.[view]'")
    sys.exit(1)
from sqlalchemy import func

from finance_app.database.connection import create_database_engine, get_session
from finance_app.database.models import AccountModel, TransactionModel


def view_accounts(session):
    """View all accounts."""
    accounts = session.query(AccountModel).order_by(AccountModel.name).all()
    
    if not accounts:
        print("No accounts found.")
        return
    
    data = []
    for acc in accounts:
        data.append([
            str(acc.id)[:8] + "...",
            acc.name,
            acc.account_type,
            acc.institution_name,
            "Closed" if acc.close_date else "Open"
        ])
    
    print("\n=== ACCOUNTS ===\n")
    print(tabulate(data, headers=["ID", "Name", "Type", "Institution", "Status"], tablefmt="grid"))


def view_transactions(session, limit=20, account_name=None):
    """View recent transactions."""
    query = session.query(TransactionModel).join(AccountModel)
    
    if account_name:
        query = query.filter(AccountModel.name.ilike(f"%{account_name}%"))
    
    transactions = query.order_by(TransactionModel.transaction_date.desc()).limit(limit).all()
    
    if not transactions:
        print("No transactions found.")
        return
    
    data = []
    for txn in transactions:
        data.append([
            txn.transaction_date.strftime("%Y-%m-%d") if txn.transaction_date else "",
            f"${txn.amount:,.2f}",
            txn.description[:40] + "..." if len(txn.description) > 40 else txn.description,
            txn.category or "",
            txn.status,
            txn.account.name[:30]
        ])
    
    print(f"\n=== RECENT TRANSACTIONS (limit: {limit}) ===\n")
    print(tabulate(data, headers=["Date", "Amount", "Description", "Category", "Status", "Account"], tablefmt="grid"))


def view_summary(session):
    """View summary statistics."""
    total_accounts = session.query(func.count(AccountModel.id)).scalar()
    total_transactions = session.query(func.count(TransactionModel.id)).scalar()
    
    # Total by account type
    account_summary = session.query(
        AccountModel.account_type,
        func.count(AccountModel.id)
    ).group_by(AccountModel.account_type).all()
    
    # Total amount by category
    category_summary = session.query(
        TransactionModel.category,
        func.sum(TransactionModel.amount)
    ).group_by(TransactionModel.category).order_by(func.sum(TransactionModel.amount).desc()).limit(10).all()
    
    print("\n=== SUMMARY ===\n")
    print(f"Total Accounts: {total_accounts}")
    print(f"Total Transactions: {total_transactions}")
    
    print("\n--- Accounts by Type ---")
    for acc_type, count in account_summary:
        print(f"  {acc_type}: {count}")
    
    print("\n--- Top Categories by Amount ---")
    for category, total in category_summary:
        if category:
            print(f"  {category}: ${float(total):,.2f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python view_data.py <database_url> [command] [options]")
        print("\nCommands:")
        print("  accounts              - View all accounts")
        print("  transactions [limit]  - View recent transactions (default: 20)")
        print("  summary               - View summary statistics")
        print("\nExample:")
        print("  python view_data.py postgresql://user:pass@localhost/finance accounts")
        print("  python view_data.py postgresql://user:pass@localhost/finance transactions 50")
        sys.exit(1)
    
    database_url = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "summary"
    
    engine = create_database_engine(database_url)
    session = get_session(engine)
    
    try:
        if command == "accounts":
            view_accounts(session)
        elif command == "transactions":
            limit = int(sys.argv[3]) if len(sys.argv) > 3 else 20
            account_name = sys.argv[4] if len(sys.argv) > 4 else None
            view_transactions(session, limit=limit, account_name=account_name)
        elif command == "summary":
            view_summary(session)
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    finally:
        session.close()

