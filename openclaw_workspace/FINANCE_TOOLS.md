# Finance sandbox — **tool policy (read this)**

## MUST (live Postgres / balances / net worth)

Use the **MCP finance tools only**. Do **not** use **`exec`** to run shell scripts or `finance_overview*.py` / `finance_overview_gateway.sh` unless the user explicitly asks you to debug the shell path **or** an MCP tool failed after retry.

Logical names (OpenClaw may display colons **`:`** or double underscores **`__`** — they refer to the same tools):

| Use case | MCP tool |
|----------|----------|
| Full snapshot JSON (accounts, net worth, unreconciled) | **`etl-finance:get_finance_snapshot`** |
| Quick DB sanity check | **`etl-finance:finance_overview_smoke`** |

Equivalent UI strings you might see: `etl-finance__get_finance_snapshot`, `etl-finance__finance_overview_smoke`.

## NEVER (unless user insists)

- `exec` → `sh /workspace/etl/scripts/finance_overview_gateway.sh`
- `exec` → raw `python3 …/finance_overview.py`

Those duplicate MCP and bypass the integration we want to test.

## Fallback

Only if MCP tools are **missing from the tool list** or **return errors** twice: then use **`sh /workspace/etl/scripts/finance_overview_gateway.sh`** and say clearly you fell back because MCP failed.

---

## Registration (operators)

```bash
export OPENCLAW_STATE_DIR="$PWD/.openclaw_runtime/config"
export OPENCLAW_CONFIG_PATH="$PWD/.openclaw_runtime/config/openclaw.json"
./scripts/register_openclaw_mcp_finance.sh
```

Restart **`etl-openclaw-gateway`** after MCP config changes if tools do not appear.

---

## Verification (operators)

-json agent turns: **`result.meta.toolSummary.tools`** should list MCP tool identifiers (often containing **`etl-finance`**), **not** plain **`exec`** for finance questions.

---

## Connection / seeding

- MCP server applies DB URL defaults inside Docker (see **`scripts/mcp_finance_server.py`**).
- Seed on host: `set -a && source .env.local && set +a && .venv/bin/python scripts/seed_sandbox.py`

---

## Cursor IDE (optional)

Host paths: `.venv/bin/python`, `scripts/mcp_finance_server.py`, repo root as `cwd`.
