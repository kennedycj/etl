#!/usr/bin/env python3
"""Replace Postgres finance data by importing ledger CSV from your archive.

Typical archive layout (FINANCE_ARCHIVE_ROOT):
  10_normalized/, 20_ledger/*.csv

Example:
  export DATABASE_URL=postgresql://...
  export FINANCE_ARCHIVE_ROOT=/Users/you/Documents/family/finances/finance_archive
  python scripts/import_archive_ledger.py --replace --yes

Ledger file selection defaults to the same priority as analyze_assets.py (see --ledger).
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance_app.database.connection import create_database_engine, create_session_factory
from finance_app.importers.ledger_csv_importer import (
    clear_finance_tables,
    import_ledger_csv,
    resolve_ledger_csv,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import ledger CSV into Postgres")
    parser.add_argument(
        "--archive-root",
        default=os.environ.get("FINANCE_ARCHIVE_ROOT", ""),
        help="Path to finance archive (or set FINANCE_ARCHIVE_ROOT)",
    )
    parser.add_argument(
        "--ledger",
        default="auto",
        help="Ledger choice: auto|with_mortgage|with_heloc|with_cds|reconciled|raw",
    )
    parser.add_argument(
        "--ledger-path",
        default="",
        help="Explicit CSV path (overrides --ledger)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing accounts/transactions before import",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required with --replace (confirmation)",
    )
    parser.add_argument(
        "--tag",
        default="imported_from_ledger_csv",
        help="Optional notes tag on newly created accounts",
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 1

    ar = args.archive_root.strip()
    if not args.ledger_path and not ar:
        print("Set --archive-root or FINANCE_ARCHIVE_ROOT.", file=sys.stderr)
        return 1

    if args.replace and not args.yes:
        print("Refused: --replace requires --yes", file=sys.stderr)
        return 1

    if args.ledger_path:
        ledger_file = os.path.abspath(args.ledger_path)
    else:
        ledger_file = str(resolve_ledger_csv(ar, args.ledger))

    engine = create_database_engine(db_url)
    SessionFactory = create_session_factory(engine)
    session = SessionFactory()

    try:
        if args.replace:
            td, ad = clear_finance_tables(session)
            print(f"Cleared database: {td} transactions, {ad} accounts.")

        ca, ti = import_ledger_csv(session, ledger_file, notes_tag=args.tag)
        print(f"Imported {ti} postings into {ca} ledger accounts ({ledger_file}).")
        return 0
    except Exception as e:
        session.rollback()
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
