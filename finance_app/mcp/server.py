"""FastMCP server: Postgres snapshot tools + ledger CSV analysis script runners."""

from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from finance_app.importers.ledger_csv_importer import (
    clear_finance_tables,
    import_ledger_csv,
    resolve_ledger_csv,
)
from finance_app.mcp import runtime
from finance_app.mcp.subprocess_runners import run_repo_script
from finance_app.agents.analysis.ledger_net_worth import compute_ledger_net_worth
from finance_app.importers.balances_importer import import_balances_from_archive, compute_net_worth_from_balances

mcp = FastMCP("etl-finance")


@mcp.tool()
def get_finance_snapshot() -> str:
    """Live finance overview from Postgres: accounts, balances, net worth, unreconciled counts. Returns JSON."""
    return runtime.snapshot_json()


@mcp.tool()
def finance_overview_smoke() -> str:
    """Smoke test: confirms at least one account exists and net_worth is computed."""
    payload = runtime.snapshot_payload()
    summary = payload["account_summary"]
    net = payload["net_worth"]
    if summary.get("total_accounts", 0) < 1:
        return "smoke failed: no accounts (import ledger or seed sandbox)."
    if "net_worth" not in net:
        return "smoke failed: missing net_worth in analyzer output."
    return "smoke OK"


@mcp.tool()
def analysis_expenses_by_year_from_ledger() -> str:
    """Run analyze_expenses.py against ledger CSV under FINANCE_ARCHIVE_ROOT (printed report)."""
    return run_repo_script("analyze_expenses.py", timeout=400)


@mcp.tool()
def analysis_assets_from_ledger() -> str:
    """Run analyze_assets.py (balance sheet style report from ledger CSV)."""
    return run_repo_script("analyze_assets.py", timeout=400)


@mcp.tool()
def analysis_income_from_ledger() -> str:
    """Run analyze_income.py using the finance archive."""
    return run_repo_script("analyze_income.py", timeout=400)


@mcp.tool()
def analysis_income_sources_from_ledger() -> str:
    """Run analyze_income_sources.py."""
    return run_repo_script("analyze_income_sources.py", timeout=400)


@mcp.tool()
def ledger_net_worth_from_archive(finance_archive_root: str = "", ledger: str = "auto") -> str:
    """Compute net worth directly from the double-entry ledger CSV (Assets/Liabilities only).

    This is ledger-native and does not depend on the Postgres import semantics.
    Returns JSON including two net worth interpretations depending on liability sign convention.
    """
    root = (finance_archive_root or os.environ.get("FINANCE_ARCHIVE_ROOT", "")).strip()
    if not root:
        return (
            "Missing finance_archive_root argument or FINANCE_ARCHIVE_ROOT environment variable. "
            "Example: set FINANCE_ARCHIVE_ROOT=/path/to/finance_archive on the gateway."
        )

    try:
        ledger_path = resolve_ledger_csv(root, ledger)
    except FileNotFoundError as e:
        return f"Error: {e}. Is FINANCE_ARCHIVE_ROOT set and mounted into the gateway?"
    res = compute_ledger_net_worth(ledger_path)

    def top(d: dict, n: int = 10):
        return sorted(((k, float(v)) for k, v in d.items()), key=lambda kv: abs(kv[1]), reverse=True)[:n]

    payload = {
        "ledger_path": res.ledger_path,
        "assets_total": float(res.assets_total),
        "liabilities_balance_sum": float(res.liabilities_balance_sum),
        "liabilities_debt_if_negative": float(res.liabilities_debt_if_negative),
        "liabilities_debt_if_positive": float(res.liabilities_debt_if_positive),
        "net_worth_assuming_liabilities_negative": float(res.net_worth_assuming_liabilities_negative),
        "net_worth_assuming_liabilities_positive": float(res.net_worth_assuming_liabilities_positive),
        "top_asset_accounts_by_abs_balance": top(res.accounts_assets),
        "top_liability_accounts_by_abs_balance": top(res.accounts_liabilities),
        "notes": [
            "This tool sums postings per account in the ledger CSV for Assets:* and Liabilities:* only.",
            "If liabilities are recorded as negative balances (common), use net_worth_assuming_liabilities_negative.",
            "If liabilities are recorded as positive balances, use net_worth_assuming_liabilities_positive.",
        ],
    }
    return json.dumps(payload, indent=2)


@mcp.tool()
def operator_import_archive_ledger_into_postgres(
    finance_archive_root: str = "",
    ledger: str = "auto",
    confirmation_phrase: str = "",
) -> str:
    """DESTRUCTIVE: deletes all Postgres accounts/transactions, then imports ledger CSV.

    Set confirmation_phrase exactly to: DELETE_ALL_FINANCE_DATA
    Requires DATABASE_URL and a readable archive (finance_archive_root arg or FINANCE_ARCHIVE_ROOT env).
    """
    if confirmation_phrase != "DELETE_ALL_FINANCE_DATA":
        return (
            "Refused. To wipe the database and reload from your archive ledger CSV, "
            "set confirmation_phrase to exactly: DELETE_ALL_FINANCE_DATA"
        )

    root = (finance_archive_root or os.environ.get("FINANCE_ARCHIVE_ROOT", "")).strip()
    if not root:
        return "Missing finance_archive_root argument or FINANCE_ARCHIVE_ROOT environment variable."

    ledger_path = resolve_ledger_csv(root, ledger)
    from finance_app.database.connection import create_database_engine, create_session_factory

    engine = create_database_engine(runtime.database_url())
    SessionFactory = create_session_factory(engine)
    session = SessionFactory()
    try:
        td, ad = clear_finance_tables(session)
        ca, ti = import_ledger_csv(session, ledger_path, notes_tag="imported_from_ledger_csv")
        return (
            f"OK. Cleared {td} transactions, {ad} accounts. "
            f"Imported {ti} postings, {ca} ledger account names from {ledger_path}."
        )
    except Exception as e:
        session.rollback()
        return f"Error: {e!r}"
    finally:
        session.close()


@mcp.tool()
def operator_import_balance_snapshots_as_of(
    as_of_date: str = "2025-12-31",
    finance_archive_root: str = "",
) -> str:
    """Upsert balance snapshots from the archive into Postgres (non-destructive).

    Sources (when present under FINANCE_ARCHIVE_ROOT):
    - mortgage_balance.csv (US Bank)
    - cd_balances.csv (Bank of America)
    - investments_balance.csv (Fidelity/Morgan Stanley/ADP/etc.)
    - loans.csv (normalized)
    """
    root = (finance_archive_root or os.environ.get("FINANCE_ARCHIVE_ROOT", "")).strip()
    if not root:
        return "Missing finance_archive_root argument or FINANCE_ARCHIVE_ROOT environment variable."

    from dateutil import parser
    cutoff = parser.parse(as_of_date)

    from finance_app.database.connection import create_database_engine, create_session_factory
    from finance_app.database.schema import create_tables

    engine = create_database_engine(runtime.database_url())
    # ensure new balances table exists
    create_tables(engine, drop_existing=False)
    SessionFactory = create_session_factory(engine)
    session = SessionFactory()
    try:
        res = import_balances_from_archive(session, root, as_of_date=cutoff)
        return json.dumps(
            {"ok": True, "imported": res, "as_of_date": cutoff.date().isoformat()},
            indent=2,
        )
    except Exception as e:
        session.rollback()
        return f"Error: {e!r}"
    finally:
        session.close()


@mcp.tool()
def net_worth_from_balance_snapshots(as_of_date: str = "2025-12-31") -> str:
    """Compute net worth from balance snapshots stored in Postgres (rigorous for as-of).

    Requires operator_import_balance_snapshots_as_of to have been run at least once.
    """
    from dateutil import parser
    cutoff = parser.parse(as_of_date)

    from finance_app.database.connection import create_database_engine, create_session_factory
    from finance_app.database.schema import create_tables

    engine = create_database_engine(runtime.database_url())
    create_tables(engine, drop_existing=False)
    SessionFactory = create_session_factory(engine)
    session = SessionFactory()
    try:
        payload = compute_net_worth_from_balances(session, as_of_date=cutoff)
        payload["ok"] = True
        return json.dumps(payload, indent=2)
    except Exception as e:
        return f"Error: {e!r}"
    finally:
        session.close()


@mcp.tool()
def tooling_script_catalog() -> str:
    """Describe how root-level Python scripts are grouped (ledger vs analysis vs tests)."""
    from finance_app.tooling.scripts_catalog import CATALOG_JSON

    return json.dumps(CATALOG_JSON, indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
