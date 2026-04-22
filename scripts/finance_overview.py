#!/usr/bin/env python3
"""Print JSON overview of the finance DB for smoke tests and agent tools.

Uses FinancialAnalyzer (net worth, account summary, unreconciled counts).

Usage:
  set -a && source .env.local && set +a
  python scripts/finance_overview.py
  python scripts/finance_overview.py --smoke

OpenClaw / shell: run with DATABASE_URL in the environment (same as above).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance_app.agents.analyzer import FinancialAnalyzer
from finance_app.database.connection import create_database_engine, create_session_factory


def main() -> int:
    parser = argparse.ArgumentParser(description="Finance DB JSON overview")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Exit 0 if at least one account exists and net worth is present",
    )
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print(
            "DATABASE_URL is not set. On the host: set -a && source .env.local && set +a. "
            "Inside the OpenClaw gateway (exec may not inherit env): "
            "sh /workspace/etl/scripts/finance_overview_gateway.sh",
            file=sys.stderr,
        )
        return 1

    engine = create_database_engine(url)
    SessionFactory = create_session_factory(engine)
    session = SessionFactory()

    try:
        analyzer = FinancialAnalyzer(session)
        summary = analyzer.get_account_summary()
        net = analyzer.get_net_worth()
        unreconciled = analyzer.get_unreconciled_transactions()

        if args.smoke:
            if summary.get("total_accounts", 0) < 1:
                print("smoke failed: no accounts (run scripts/seed_sandbox.py)", file=sys.stderr)
                return 1
            if "net_worth" not in net:
                print("smoke failed: missing net_worth", file=sys.stderr)
                return 1
            print("smoke OK")
            return 0

        payload = {
            "ok": True,
            "account_summary": summary,
            "net_worth": net,
            "unreconciled": unreconciled,
        }
        print(json.dumps(payload, indent=2))
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
