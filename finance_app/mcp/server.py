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
def tooling_script_catalog() -> str:
    """Describe how root-level Python scripts are grouped (ledger vs analysis vs tests)."""
    from finance_app.tooling.scripts_catalog import CATALOG_JSON

    return json.dumps(CATALOG_JSON, indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
