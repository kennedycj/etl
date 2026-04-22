"""Import double-entry ledger CSV rows into AccountModel / TransactionModel."""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Tuple
from uuid import uuid4

from sqlalchemy.orm import Session

from finance_app.database.models import AccountModel, TransactionModel
from finance_app.models.common import ReconcileStatus


def infer_account_metadata(ledger_account_path: str) -> Tuple[str, str]:
    """Return (account_type, institution_name) from a ledger path like Assets:BankOfAmerica:Checking."""
    raw = ledger_account_path.strip()
    parts = raw.split(":")

    inst = parts[1].replace("_", " ") if len(parts) >= 2 else "Unknown"

    prefix = parts[0] if parts else ""
    tail = parts[-1].lower() if parts else ""

    if prefix == "Expenses":
        return "expense", inst
    if prefix == "Income":
        return "income", inst
    if prefix == "Equity":
        return "equity", inst

    if prefix == "Liabilities":
        low = raw.lower()
        if "credit" in low or "visa" in low or "amex" in low:
            return "credit_card", inst
        if "heloc" in low or "home equity" in low:
            return "heloc", inst
        if "mortgage" in low:
            return "mortgage", inst
        return "credit_card", inst

    # Assets
    if "cd" in tail or "certificate" in tail:
        return "cd", inst
    if "savings" in tail:
        return "savings", inst
    if "checking" in tail or "chk" in tail:
        return "checking", inst
    if "brokerage" in tail or "investment" in tail:
        return "brokerage", inst

    return "checking", inst


def clear_finance_tables(session: Session) -> Tuple[int, int]:
    """Delete all transactions then accounts. Returns (transactions_deleted, accounts_deleted)."""
    txn = session.query(TransactionModel).delete(synchronize_session=False)
    acct = session.query(AccountModel).delete(synchronize_session=False)
    session.commit()
    return txn, acct


def import_ledger_csv(session: Session, ledger_csv_path: Path | str, *, notes_tag: str | None = None) -> Tuple[int, int]:
    """Import ledger postings as one TransactionModel row per CSV line.

    Ledger columns: date,description,account,amount,source_file,transaction_id (transaction_id optional).
    """
    path = Path(ledger_csv_path)
    if not path.is_file():
        raise FileNotFoundError(path)

    accounts_cache: dict[str, AccountModel] = {}
    created_accounts = 0
    txn_count = 0

    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            acct_name = (row.get("account") or "").strip()
            if not acct_name:
                continue
            date_s = (row.get("date") or "").strip()
            amount_s = (row.get("amount") or "").strip()
            if not date_s or not amount_s:
                continue

            if acct_name not in accounts_cache:
                acc_type, inst = infer_account_metadata(acct_name)
                account = AccountModel(
                    id=uuid4(),
                    name=acct_name,
                    account_type=acc_type,
                    institution_name=inst,
                    currency="USD",
                    open_date=datetime.utcnow(),
                    notes=notes_tag,
                )
                session.add(account)
                session.flush()
                accounts_cache[acct_name] = account
                created_accounts += 1

            account = accounts_cache[acct_name]
            transaction_date = datetime.strptime(date_s[:10], "%Y-%m-%d")
            amount = Decimal(str(amount_s).replace(",", ""))
            desc = (row.get("description") or "").strip() or "(no description)"
            src = (row.get("source_file") or "").strip()
            memo_bits = [src] if src else []
            tid = (row.get("transaction_id") or "").strip()
            if tid:
                memo_bits.append(f"id:{tid}")

            txn = TransactionModel(
                id=uuid4(),
                account_id=account.id,
                transaction_date=transaction_date,
                amount=amount,
                currency="USD",
                description=desc,
                category=acct_name.split(":")[-1][:100] if ":" in acct_name else None,
                status="posted",
                reconcile_status=ReconcileStatus.RECONCILED,
                memo=" | ".join(memo_bits) if memo_bits else None,
                is_external=True,
            )
            session.add(txn)
            txn_count += 1

    session.commit()
    return created_accounts, txn_count


def resolve_ledger_csv(archive_root: Path | str, preference: str = "auto") -> Path:
    """Pick ledger file under archive_root/20_ledger (same priority family as analyze_assets)."""
    root = Path(archive_root).expanduser()
    ld = root / "20_ledger"
    if not ld.is_dir():
        raise FileNotFoundError(f"Missing ledger directory: {ld}")

    auto_order = [
        "ledger_with_mortgage.csv",
        "ledger_with_heloc.csv",
        "ledger_with_cds.csv",
        "ledger_reconciled.csv",
        "ledger.csv",
    ]
    explicit = {
        "with_mortgage": "ledger_with_mortgage.csv",
        "with_heloc": "ledger_with_heloc.csv",
        "with_cds": "ledger_with_cds.csv",
        "reconciled": "ledger_reconciled.csv",
        "raw": "ledger.csv",
    }

    pref = preference.strip().lower()
    if pref == "auto":
        for name in auto_order:
            p = ld / name
            if p.is_file():
                return p
        raise FileNotFoundError(f"No ledger CSV found in {ld}")

    if pref in explicit:
        p = ld / explicit[pref]
        if not p.is_file():
            raise FileNotFoundError(p)
        return p

    raise ValueError(f"Unknown ledger preference: {preference} (use auto|with_mortgage|...|raw)")
