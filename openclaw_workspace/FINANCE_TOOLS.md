# Finance sandbox — **tool policy (read this)**

## MUST (live Postgres / balances / net worth)

Use the **MCP finance tools only**. Do **not** use **`exec`** for finance scripts unless the user asks for shell debugging **or** MCP failed twice.

OpenClaw may display tools as **`etl-finance__tool_name`** (double underscore) instead of **`etl-finance:tool_name`**.

### Postgres-backed

| MCP tool | Purpose |
|----------|---------|
| **`get_finance_snapshot`** | Full JSON: accounts, balances, net worth, unreconciled |
| **`finance_overview_smoke`** | Quick DB sanity text |

### Ledger CSV reports (needs **`FINANCE_ARCHIVE_ROOT`** on the gateway host)

Runs the same repo-root **`analyze_*.py`** scripts you use locally (stdout captured).

| MCP tool | Script |
|----------|--------|
| **`analysis_expenses_by_year_from_ledger`** | `analyze_expenses.py` |
| **`analysis_assets_from_ledger`** | `analyze_assets.py` |
| **`analysis_income_from_ledger`** | `analyze_income.py` |
| **`analysis_income_sources_from_ledger`** | `analyze_income_sources.py` |

### Operators & catalog

| MCP tool | Purpose |
|----------|---------|
| **`operator_import_archive_ledger_into_postgres`** | **Destructive**: wipe Postgres accounts/transactions and reload from ledger CSV under `finance_archive_root`. Requires confirmation phrase **`DELETE_ALL_FINANCE_DATA`** and **`DATABASE_URL`**. |
| **`tooling_script_catalog`** | JSON map of how repo-root scripts are grouped (ledger vs analysis vs tests). |

## NEVER (unless user insists)

- `exec` → `finance_overview_gateway.sh` / raw `python3 …/finance_overview.py`

## Fallback

If MCP tools are missing or error twice: **`sh /workspace/etl/scripts/finance_overview_gateway.sh`**.

---

## Reload real data from your archive (human operator)

On the **host** (after `DATABASE_URL` and archive path):

```bash
export FINANCE_ARCHIVE_ROOT=/path/to/finance_archive
export DATABASE_URL=postgresql://...
.venv/bin/python scripts/import_archive_ledger.py --replace --yes --ledger auto
```

`--ledger auto` picks the richest ledger CSV present (`ledger_with_mortgage.csv`, … `ledger.csv`).

---

## Registration (operators)

```bash
export OPENCLAW_STATE_DIR="$PWD/.openclaw_runtime/config"
export OPENCLAW_CONFIG_PATH="$PWD/.openclaw_runtime/config/openclaw.json"
./scripts/register_openclaw_mcp_finance.sh
```

Rebuild/restart **`etl-openclaw-gateway`** after changing Python deps or MCP code.

---

## Verification

Agent `--json`: **`result.meta.toolSummary.tools`** should list **`etl-finance__…`** for MCP-driven answers.

---

## Cursor IDE (optional)

Host: `.venv/bin/python`, `scripts/mcp_finance_server.py`, `cwd` = repo root.
