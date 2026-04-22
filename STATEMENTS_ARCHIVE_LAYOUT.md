# Statements of record (archive root)

External, validated facts live **next to** the ledger pipeline — not inside `10_normalized/` or `20_ledger/`.

**Base path:** `<FINANCE_ARCHIVE_ROOT>/statements/`

Drop originals here (PDF preferred). Use **ISO dates** in filenames when you know as-of or statement period end.

```
statements/
  property/
    home_value/
      2025-06-01_county_tax_assessment.pdf
  mortgage/
    2025-12-01_us_bank_mortgage_statement.pdf
  heloc/
    2025-12-01_us_bank_heloc_statement.pdf
  taxes/
    federal/
      2024_1040.pdf
    state/
      2024_mn_return.pdf
  income/
    spouse/
      2024_W2.pdf
    household/
      2024_schedule_misc.pdf
  retirement/
    fidelity/
      2025-12-31_statement.pdf
    adp/
      2025-12-31_statement.pdf
  banking/
    bank_of_america/
      2025-12-31_statement.pdf
```

**Naming:** `YYYY-MM-DD_<short_description>.pdf` — if date unknown, prefix `unknown_`.

ETL will index and extract from these paths; nothing here replaces the ledger — it **grounds** balances and taxes that the ledger alone cannot.
