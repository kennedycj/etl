"""Import point-in-time balances from archive CSVs into AccountBalanceModel."""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from finance_app.database.models import AccountBalanceModel, AccountModel
from finance_app.importers.ledger_csv_importer import resolve_ledger_csv


def _parse_date(s: str) -> datetime:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    # fall back to dateutil if present
    from dateutil import parser

    return parser.parse(s)


def _dec(s: str) -> Decimal:
    return Decimal(str(s).replace(",", "").strip())


def _upsert_balance(
    session: Session,
    *,
    account_name: str,
    account_type: str,
    institution_name: str,
    as_of_date: datetime,
    balance: Decimal,
    currency: str = "USD",
    source: str,
    source_file_path: str,
    notes: str | None = None,
) -> None:
    existing = (
        session.query(AccountBalanceModel)
        .filter(AccountBalanceModel.account_name == account_name)
        .filter(AccountBalanceModel.as_of_date == as_of_date)
        .first()
    )
    if existing:
        existing.balance = balance
        existing.account_type = account_type
        existing.institution_name = institution_name
        existing.currency = currency
        existing.source = source
        existing.source_file_path = source_file_path
        existing.notes = notes
        return

    # try link to accounts table by name
    acc = session.query(AccountModel).filter(AccountModel.name == account_name).first()
    ab = AccountBalanceModel(
        account_id=acc.id if acc else None,
        account_name=account_name,
        account_type=account_type,
        institution_name=institution_name,
        as_of_date=as_of_date,
        balance=balance,
        currency=currency,
        source=source,
        source_file_path=source_file_path,
        notes=notes,
    )
    session.add(ab)


def import_mortgage_balance_csv(
    session: Session, file_path: Path, *, as_of_cutoff: datetime
) -> int:
    """Import latest mortgage principal balance <= cutoff as a liability (positive debt)."""
    rows: List[dict] = []
    with file_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    if not rows:
        return 0

    eligible = []
    for r in rows:
        dt = _parse_date(r.get("statement_date", ""))
        if dt <= as_of_cutoff:
            eligible.append((dt, r))
    if not eligible:
        return 0

    dt, r = sorted(eligible, key=lambda x: x[0])[-1]
    bal = _dec(r.get("principal_balance", "0"))
    _upsert_balance(
        session,
        account_name="Liabilities:Mortgage:USBank",
        account_type="mortgage",
        institution_name="USBank",
        as_of_date=dt,
        balance=bal,  # positive debt
        source="mortgage_balance",
        source_file_path=str(file_path),
        notes=r.get("notes") or None,
    )
    return 1


def import_loans_csv(session: Session, file_path: Path, *, as_of_cutoff: datetime) -> int:
    """Import latest loan balances per account <= cutoff as liabilities (positive debt)."""
    count = 0
    # best row per loan account_name
    best: dict[str, tuple[datetime, dict]] = {}
    with file_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            dt = _parse_date(r.get("statement_date", ""))
            if dt > as_of_cutoff:
                continue
            key = (r.get("account_name") or "").strip() or (r.get("loan_type") or "loan")
            prev = best.get(key)
            if not prev or dt > prev[0]:
                best[key] = (dt, r)

    for key, (dt, r) in best.items():
        lender = (r.get("lender") or "Unknown").strip()
        loan_type = (r.get("loan_type") or "loan").strip()
        masked = (r.get("account_number_masked") or "").strip()
        bal = _dec(r.get("principal_balance", "0"))
        acct_name = f"Liabilities:{loan_type.title().replace(' ', '')}:{lender}"
        if masked:
            acct_name += f":{masked}"
        _upsert_balance(
            session,
            account_name=acct_name,
            account_type="loan",
            institution_name=lender,
            as_of_date=dt,
            balance=bal,
            source="loans_csv",
            source_file_path=str(file_path),
            notes=r.get("notes") or None,
        )
        count += 1
    return count


def import_cd_balances_csv(session: Session, file_path: Path, *, as_of_cutoff: datetime) -> int:
    """Import latest CD balances per cd_id <= cutoff as assets (positive)."""
    count = 0
    best: dict[str, tuple[datetime, dict]] = {}
    with file_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            dt = _parse_date(r.get("statement_date", ""))
            if dt > as_of_cutoff:
                continue
            cd_id = (r.get("cd_id") or "").strip()
            if not cd_id:
                continue
            prev = best.get(cd_id)
            if not prev or dt > prev[0]:
                best[cd_id] = (dt, r)

    for cd_id, (dt, r) in best.items():
        bal = _dec(r.get("balance", "0"))
        _upsert_balance(
            session,
            account_name=f"Assets:BankOfAmerica:CD:{cd_id}",
            account_type="cd",
            institution_name="BankOfAmerica",
            as_of_date=dt,
            balance=bal,
            source="cd_balances",
            source_file_path=str(file_path),
            notes=f"next_maturity={r.get('next_maturity_date')}; rate={r.get('interest_rate')}; apy={r.get('apy')}",
        )
        count += 1
    return count


def _normalize_investment_type(t: str) -> str:
    s = (t or "").strip().lower()
    if s in {"529"}:
        return "529"
    if "401" in s:
        return "401k"
    if "able" in s:
        return "able"
    if "rollover" in s and "ira" in s:
        return "ira_rollover"
    if "ira" in s:
        return "ira_traditional"
    if "individual" in s or "brokerage" in s:
        return "brokerage"
    return "brokerage"


def import_investments_balance_csv(
    session: Session, file_path: Path, *, as_of_cutoff: datetime
) -> int:
    """Import investment account values (assets, positive)."""
    count = 0
    with file_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            dt = _parse_date(r.get("statement_date", ""))
            if dt > as_of_cutoff:
                continue
            value = _dec(r.get("account_value", "0"))
            acct_type = _normalize_investment_type(r.get("account_type", ""))
            inst = (r.get("institution") or "Unknown").strip()
            name = (r.get("account_name") or "").strip() or f"{acct_type}:{inst}"
            _upsert_balance(
                session,
                account_name=f"Assets:{inst}:{name}",
                account_type=acct_type,
                institution_name=inst,
                as_of_date=dt,
                balance=value,
                source="investments_balance",
                source_file_path=str(file_path),
                notes=r.get("notes") or None,
            )
            count += 1
    return count


def import_balances_from_archive(session: Session, archive_root: Path | str, *, as_of_date: datetime) -> dict:
    root = Path(archive_root).expanduser()
    # Mirror the container mapping used elsewhere
    if str(root).startswith("/Users/") and Path("/data/finance_archive").is_dir():
        root = Path("/data/finance_archive")

    out = {"mortgage": 0, "cds": 0, "investments": 0, "loans": 0}

    mort = root / "00_raw" / "bank" / "us_bank" / "mortgage" / "mortgage_balance.csv"
    if mort.is_file():
        out["mortgage"] = import_mortgage_balance_csv(session, mort, as_of_cutoff=as_of_date)

    loans = root / "10_normalized" / "loans" / "loans.csv"
    if loans.is_file():
        out["loans"] = import_loans_csv(session, loans, as_of_cutoff=as_of_date)

    cds = root / "00_raw" / "bank" / "bank_of_america" / "cd_balances.csv"
    if cds.is_file():
        out["cds"] = import_cd_balances_csv(session, cds, as_of_cutoff=as_of_date)

    inv = root / "10_normalized" / "investments" / "investments_balance.csv"
    if inv.is_file():
        out["investments"] = import_investments_balance_csv(session, inv, as_of_cutoff=as_of_date)

    session.commit()
    return out


def compute_net_worth_from_balances(
    session: Session, *, as_of_date: datetime
) -> dict:
    """Compute net worth using latest balance <= as_of_date for each account_name."""
    # Pull all balances <= cutoff; pick latest per account_name
    rows = (
        session.query(AccountBalanceModel)
        .filter(AccountBalanceModel.as_of_date <= as_of_date)
        .order_by(AccountBalanceModel.account_name.asc(), AccountBalanceModel.as_of_date.desc())
        .all()
    )
    latest: dict[str, AccountBalanceModel] = {}
    for r in rows:
        if r.account_name not in latest:
            latest[r.account_name] = r

    assets = Decimal("0")
    liabilities = Decimal("0")
    assets_by_type: dict[str, Decimal] = {}
    liabilities_by_type: dict[str, Decimal] = {}

    for r in latest.values():
        t = (r.account_type or "").lower()
        if t in {"mortgage", "heloc", "loan", "credit_card"}:
            liabilities += Decimal(r.balance)
            liabilities_by_type[t] = liabilities_by_type.get(t, Decimal("0")) + Decimal(r.balance)
        else:
            assets += Decimal(r.balance)
            assets_by_type[t or "unknown"] = assets_by_type.get(t or "unknown", Decimal("0")) + Decimal(r.balance)

    return {
        "as_of_date": as_of_date.date().isoformat(),
        "accounts_with_balances": len(latest),
        "assets": float(assets),
        "liabilities": float(liabilities),
        "net_worth": float(assets - liabilities),
        "assets_by_type": {k: float(v) for k, v in assets_by_type.items()},
        "liabilities_by_type": {k: float(v) for k, v in liabilities_by_type.items()},
    }

