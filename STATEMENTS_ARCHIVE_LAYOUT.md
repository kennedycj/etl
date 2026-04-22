# Statements of record (archive root)

Validated external documents live **next to** the ledger pipeline — not inside `10_normalized/` or `20_ledger/`.

**Base path:** `<FINANCE_ARCHIVE_ROOT>/statements/`

## Division of labor

| Layer | Role |
|-------|------|
| **You** | Drop originals (PDF preferred). One shallow folder per broad theme. Optional date in the filename when you know it. |
| **ETL** | Scan, hash, extract structured fields; infer institution, account type, and dates when the document supports it. |
| **Agent** | Fill gaps via chat when a PDF is ambiguous or metadata is missing. |

Paths do **not** encode broker, bank, retirement vs taxable, or product names — that belongs in extracted data or conversation.

## Layout (single layer under `statements/`)

```
statements/
  inbox/
  tax/
  property/
  loans/
  accounts/
```

| Folder | Use for |
|--------|---------|
| **inbox** | Anything you are not ready to sort — tools and agents can move or classify later. |
| **tax** | Returns, filings, notices, income-reporting forms (e.g. W-2, 1099), assessments **from tax authorities**. |
| **property** | Real-estate and fixed-asset paperwork: deeds, appraisals, county records, homeowner/HOA/major asset insurance tied to a place or thing. |
| **loans** | Lender-issued statements for mortgages, HELOCs, lines of credit, auto/student/other installment debt — wherever **balance and terms** live on the statement. |
| **accounts** | Institution-issued **account** statements: deposits, brokerage, custodial, payroll provider exports, HSAs — anything that reads like “here is your account for this period.” |

If a document fits two buckets, pick one and rely on filename + extraction; perfection is optional.

## Filenames

Prefer **`YYYY-MM-DD_short_label.pdf`** when you know an as-of or statement end date. If unknown, **`unknown_short_label.pdf`** is fine.

---

## Database persistence & privacy

OpenClaw in a container typically **cannot read** files under your archive (by design). ETL runs where the archive is mounted and writes **only** into Postgres using a strict policy:

| Stored | Not stored |
|--------|------------|
| Path under `statements/`, `sha256`, bucket, size, extraction status | Raw PDF bytes |
| **`financial_facts`** JSON: amounts, tax lines, balances, filing year, categories **after** sanitization | Full OCR/text transcript, names, addresses, emails, phones, DOB |
| | **SSN, ITIN, account numbers, routing numbers** — blocked by key list and pattern redaction; pipeline **refuses** to persist if SSN-shaped data remains |

Implementation: `finance_app.statements.redaction.prepare_financial_facts_for_persistence()` must run on every blob before insert/update. MCP tools must return **sanitized DB fields** only (never raw extraction).

Agents only see what the tools return; treating the DB as the durable, minimised source keeps privacy boundaries clear.

---

Nothing here replaces the ledger; it **grounds** balances and obligations the ledger alone may not capture.
