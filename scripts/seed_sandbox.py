#!/usr/bin/env python3
"""Insert fake sandbox accounts and transactions for local testing.

Requires DATABASE_URL (e.g. from .env.local). Idempotent: skips if sandbox data
already exists unless --reset.

Usage:
  set -a && source .env.local && set +a
  python scripts/seed_sandbox.py
  python scripts/seed_sandbox.py --reset --yes   # wipe prior sandbox rows and re-seed
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

# Repo root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from finance_app.database.connection import create_database_engine, create_session_factory
from finance_app.database.models import AccountModel, TransactionModel
from finance_app.models.common import ReconcileStatus, TransactionType

SANDBOX_NOTE = "SANDBOX_SEED_V1"

# Stable UUIDs so docs/tests can reference them
ID_CHECKING = UUID("11111111-1111-4111-8111-111111111101")
ID_SAVINGS = UUID("11111111-1111-4111-8111-111111111102")
ID_CREDIT = UUID("11111111-1111-4111-8111-111111111103")
ID_CD = UUID("11111111-1111-4111-8111-111111111104")


def _delete_sandbox(session: Session) -> None:
    ids = [
        row[0]
        for row in session.query(AccountModel.id).filter(AccountModel.notes.contains(SANDBOX_NOTE)).all()
    ]
    if not ids:
        return
    session.query(TransactionModel).filter(TransactionModel.account_id.in_(ids)).delete(
        synchronize_session=False
    )
    session.query(AccountModel).filter(AccountModel.id.in_(ids)).delete(synchronize_session=False)


def seed(session: Session) -> None:
    base = datetime(2025, 12, 1, 12, 0, 0)

    checking = AccountModel(
        id=ID_CHECKING,
        name="Sandbox Checking",
        account_type="checking",
        institution_name="Fake National Bank",
        account_number_masked="0001",
        currency="USD",
        open_date=base,
        notes=f"{SANDBOX_NOTE} primary cash",
    )
    savings = AccountModel(
        id=ID_SAVINGS,
        name="Sandbox Savings",
        account_type="savings",
        institution_name="Fake National Bank",
        account_number_masked="0002",
        currency="USD",
        open_date=base,
        notes=SANDBOX_NOTE,
    )
    credit = AccountModel(
        id=ID_CREDIT,
        name="Sandbox Visa",
        account_type="credit_card",
        institution_name="Fake Card Co",
        account_number_masked="4242",
        currency="USD",
        open_date=base,
        notes=SANDBOX_NOTE,
    )
    cd = AccountModel(
        id=ID_CD,
        name="Sandbox 12mo CD",
        account_type="cd",
        institution_name="Fake National Bank",
        account_number_masked="0003",
        currency="USD",
        open_date=base,
        notes=f"{SANDBOX_NOTE} matures 2026-04-30 (fake)",
    )
    session.add_all([checking, savings, credit, cd])

    def tx(
        account_id: UUID,
        days: int,
        amount: Decimal,
        description: str,
        category: str | None,
        reconcile: ReconcileStatus = ReconcileStatus.RECONCILED,
    ) -> TransactionModel:
        return TransactionModel(
            account_id=account_id,
            transaction_date=base + timedelta(days=days),
            amount=amount,
            currency="USD",
            description=description,
            category=category,
            transaction_type=TransactionType.PURCHASE if amount < 0 else TransactionType.DEPOSIT,
            status="posted",
            reconcile_status=reconcile,
        )

    # Checking: payroll + expenses (balance sums to +9,750)
    session.add(
        tx(ID_CHECKING, 0, Decimal("10000.00"), "OPENING BALANCE / seed deposit", "transfer")
    )
    session.add(tx(ID_CHECKING, 3, Decimal("-75.50"), "GROCERY STORE", "groceries"))
    session.add(tx(ID_CHECKING, 5, Decimal("-174.25"), "UTILITY CO", "utilities"))

    # Savings
    session.add(tx(ID_SAVINGS, 1, Decimal("25000.00"), "Initial savings funding", "transfer"))

    # Credit card: debt (negative sum => liability)
    session.add(tx(ID_CREDIT, 2, Decimal("-450.00"), "ONLINE MART", "shopping"))
    session.add(tx(ID_CREDIT, 4, Decimal("-89.99"), "STREAMING", "subscriptions"))
    session.add(
        tx(
            ID_CREDIT,
            6,
            Decimal("-25.00"),
            "COFFEE SHOP",
            "dining",
            reconcile=ReconcileStatus.UNRECONCILED,
        )
    )

    # CD: single funding
    session.add(tx(ID_CD, 1, Decimal("20000.00"), "CD opening deposit", "transfer"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed sandbox finance data")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove prior sandbox rows (accounts tagged with sandbox note) then seed",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="With --reset, skip confirmation",
    )
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set. Example: set -a && source .env.local && set +a", file=sys.stderr)
        return 1

    engine = create_database_engine(url)
    SessionFactory = create_session_factory(engine)
    session = SessionFactory()

    try:
        existing = (
            session.query(AccountModel).filter(AccountModel.notes.contains(SANDBOX_NOTE)).first()
        )
        if existing and not args.reset:
            print("Sandbox data already present. Use --reset --yes to replace.")
            return 0

        if args.reset:
            if not args.yes:
                print("Add --yes to confirm reset of sandbox-tagged accounts/transactions.", file=sys.stderr)
                return 1
            _delete_sandbox(session)
            session.commit()

        seed(session)
        session.commit()
        print("Sandbox seed complete (fake data only).")
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
