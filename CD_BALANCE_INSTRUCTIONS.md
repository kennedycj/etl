# Manual CD Balance Entry Guide

## Quick Start

1. **Create the template** (if not already created):
   ```powershell
   python add_cds_to_ledger.py
   ```
   This creates `cd_balances.csv` in your CD directory.

2. **Fill in the CSV file:**
   - Open: `C:\Users\19527\Documents\finance_archive\00_raw\bank\bank_of_america\cd_balances.csv`
   - Fill in the `balance` column (and optionally other fields like `next_maturity_date`, `interest_rate`, `apy`)
   - Save the file

3. **Add CDs to ledger:**
   ```powershell
   python add_cds_to_ledger.py
   ```
   This will read the CSV and add CD balances to your ledger.

## CSV Format

The CSV has the following columns:
- `cd_id`: Last 4 digits of account number (auto-filled from filename)
- `balance`: Current CD balance (REQUIRED - fill this in)
- `statement_date`: Statement date (auto-filled from filename)
- `next_maturity_date`: Optional - next maturity date (format: YYYY-MM-DD)
- `interest_rate`: Optional - interest rate as decimal (e.g., 0.0365 for 3.65%)
- `apy`: Optional - Annual Percentage Yield as decimal

## Example

```csv
cd_id,balance,statement_date,next_maturity_date,interest_rate,apy
0534,20000.00,2026-07-03,2026-07-03,0.0359,0.0365
2781,25000.00,2025-12-29,2025-12-29,0.0400,0.0405
6512,20000.00,2026-02-01,2026-02-01,0.0380,0.0385
7280,15000.00,2026-07-15,2026-07-15,0.0375,0.0380
9703,20000.00,2026-04-30,2026-04-30,0.0360,0.0365
```

## Notes

- Only `cd_id` and `balance` are required
- Other fields are optional but helpful for analysis
- You can update the CSV anytime and re-run `add_cds_to_ledger.py` to update the ledger
- The script will create `ledger_with_cds.csv` in your `20_ledger/` directory

