"""Classification of repo-root *.py scripts (documentation for humans + MCP tooling_catalog)."""

from __future__ import annotations

CATALOG_JSON: dict[str, dict[str, object]] = {
    "ledger_archive_pipeline": {
        "description": (
            "Build ledger CSV/Beancount files under FINANCE_ARCHIVE_ROOT; "
            "normalize/reconcile postings in the filesystem before DB import."
        ),
        "scripts": [
            "process_archive.py",
            "build_ledger.py",
            "rebuild_ledger.py",
            "reconcile_accounts.py",
            "add_cds_to_ledger.py",
            "add_heloc_to_ledger.py",
            "add_mortgage_to_ledger.py",
            "add_home_value.py",
            "extract_heloc_to_csv.py",
            "ledger.py",
        ],
    },
    "postgres_import_export": {
        "description": "Move data between files and Postgres.",
        "scripts": [
            "create_tables.py",
            "import_tsv.py",
            "scripts/import_archive_ledger.py",
            "scripts/seed_sandbox.py",
            "scripts/finance_overview.py",
            "scripts/finance_overview_gateway.sh",
            "view_data.py",
            "setup_database_user.py",
        ],
    },
    "analysis_reports": {
        "description": "Read ledger CSV under the archive and print reports (mostly stdout).",
        "scripts": [
            "analyze_assets.py",
            "analyze_expenses.py",
            "analyze_income.py",
            "analyze_income_sources.py",
            "finance_agent.py",
        ],
    },
    "database_validation": {
        "description": "Consistency checks against schema or pipelines.",
        "scripts": [
            "run_validations.py",
            "schema.py",
            "check_database_location.py",
        ],
    },
    "automated_tests": {
        "description": "pytest-style or ad-hoc tests — not wired to MCP by default.",
        "scripts": [
            "test_account_model.py",
            "test_database_models.py",
            "test_data_pipeline.py",
            "test_deduplication.py",
            "test_ingestion.py",
            "test_ledger.py",
            "test_schema.py",
        ],
    },
}
