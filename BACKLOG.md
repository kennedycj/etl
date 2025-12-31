# Backlog

Items documented here are enhancements and improvements planned for future development.

## Data Curation & Ingestion

### Institution Inference Enhancement
**Priority:** Medium  
**Status:** Backlog

**Problem:**
Current institution detection (`detect_institution_from_filename`) is fragile and idiosyncratic:
- Relies on filename patterns (e.g., "boa", "chase")
- Fragile to variations in naming conventions
- Doesn't handle edge cases well
- User's file organization may not match expected patterns

**Proposed Solutions:**
1. **SLM-based inference (Preferred):**
   - Use a Small Language Model (e.g., Ollama) to analyze:
     - File path context
     - File metadata
     - Initial rows of data (transaction patterns)
     - Institution name detection from transaction descriptions
   - More robust and adaptable to user's file organization

2. **User adjudication fallback:**
   - Prompt user to confirm/adjudicate institution name when inference is uncertain
   - Store user corrections to improve future inference
   - Interactive mode for bulk imports

**Implementation Notes:**
- Keep current heuristic as fallback
- Add confidence scoring for inference
- Integrate with agent orchestration layer when available
- Consider caching user adjudications by file path patterns

---

## CD (Certificate of Deposit) Processing

### PDF Parsing for CD Statements
**Priority:** Medium  
**Status:** Structure created, PDF parsing pending

**Current State:**
- CD directory structure in place (`00_raw/cds/`)
- CD processor module created with templates
- Normalized structure defined (`10_normalized/cds/`)

**What's Needed:**
1. **PDF Text Extraction:**
   - Parse CD statement PDFs to extract:
     - Account number, nickname
     - Balance, dates (opening, renewal, maturity)
     - Interest rates (current rate, APY)
     - Interest amounts (accrued, paid, withheld)
   - Consider using `pdfplumber` or `PyPDF2` library

2. **CD Registry CSV:**
   - One row per CD with metadata
   - Fields: cd_id, institution, account_number_masked, term_months, open_date, etc.

3. **CD Snapshots CSV:**
   - Periodic state snapshots (opening, renewals, year-end)
   - Fields: date, cd_id, balance, interest_accrued, interest_paid_ytd, etc.

4. **CD Cashflows CSV:**
   - Bridge to checking account transactions
   - Tracks: interest payments, maturity principal, renewals
   - Links CD events to checking account transactions

**Benefits:**
- Accurate net worth calculation (include CDs as assets)
- Ladder strategy analysis (maturity dates, coverage)
- Tax planning (interest accrual vs. paid)
- Emergency fund tracking ($100K ladder goal)

**Implementation Notes:**
- PDFs are source of truth (no transaction feeds)
- CDs are stateful assets, not transaction accounts
- Need to link CD cashflows to checking account transactions
- Keep PDFs in `00_raw/cds/`, normalize to `10_normalized/cds/`

---

## Account Matching & Reconciliation

### Credit Card Payment Matching (COMPLETED)
**Priority:** High  
**Status:** ✅ Completed

**Problem:**
Credit card payments appear as two separate, incorrect transactions:
1. Checking account shows: `Assets:Checking` → `Liabilities:CreditCards:BankOfAmerica` (wrong card)
2. Credit card shows: `Liabilities:CreditCards:AmericanExpress` → `Expenses:Uncategorized` (uninformative)

**Solution Implemented:**
- Intelligent matching algorithm that identifies related transactions across accounts
- Matching criteria:
  - Exact amount match (within $0.01)
  - Date match (same day or within 3 days, configurable)
  - Card name extraction from descriptions and account paths
  - Source file matching
  - Description pattern matching
- Confidence scoring (minimum 60% threshold)
- Creates corrected double-entry transactions: `Assets:Checking` → `Liabilities:CreditCards:CorrectCard`
- Generates reconciled ledger with incorrect entries removed

**Files:**
- `finance_app/agents/ledger/account_matcher.py`: Core matching logic
- `reconcile_accounts.py`: Standalone reconciliation script
- Integrated into `build_ledger.py` for automatic reconciliation

**Output Files:**
- `ledger_corrected.csv`: Only the corrected entries (224 entries for 112 matches)
- `ledger_reconciled.csv`: Full ledger with corrections applied
- `reconciliation_report.txt`: Detailed match report with confidence scores

**Future Enhancements:**
- Database-backed matching for efficiency (currently uses CSV)
- Fuzzy matching for amounts with small differences
- Machine learning for confidence scoring
- Support for other inter-account transfers (loan payments, investment contributions)
- Real-time matching during ledger creation (pre-processing)

---

## Mortgage & Home Equity Tracking
**Priority:** High  
**Status:** ✅ Completed (Principal Balance Only)

**Problem:**
Mortgage payments are currently tracked incorrectly:
- All payment components (principal + interest + escrow) treated as liability reduction
- No breakdown of payment components
- Balance inferred from payments, not from actual statements
- No home value tracking
- No equity calculation

**Solution Implemented:**
1. **Mortgage Statement Processing:**
   - Created `mortgage_processor.py` to extract key data from US Bank mortgage statements (PDFs/text).
   - Extracts: outstanding principal balance, interest rate, maturity date, and payment breakdown (principal, interest, escrow, taxes, insurance).
   - OCR fallback for image-based PDFs (requires Poppler).
   - CSV template for manual entry as a fallback.
2. **Ledger Structure:**
   - `Liabilities:Mortgage:USBank`: Tracks the outstanding principal balance (from statements).
   - `Assets:RealEstate:PrimaryResidence`: Tracked via `home_value.csv` in `10_normalized/real_estate/`.
   - Home equity calculated as `Home Value - Mortgage Principal - HELOC Principal` in `analyze_assets.py`.
3. **Implementation:**
   - `finance_app/agents/ledger/mortgage_processor.py` for PDF/text extraction.
   - `add_mortgage_to_ledger.py` script to add mortgage balance to the ledger.
   - `add_home_value.py` script to manage home value entries from a CSV.
   - `analyze_assets.py` updated to:
     - Read home value from `10_normalized/real_estate/home_value.csv`.
     - Read mortgage and HELOC balances from the ledger.
     - Calculate and display `Home Equity`.
     - Use `ledger_with_mortgage.csv` as the most complete ledger.

**Remaining Work:**
- Mortgage payment breakdown (principal, interest, escrow) into separate ledger entries (future enhancement).

**Files:**
- `finance_app/agents/ledger/mortgage_processor.py`
- `add_mortgage_to_ledger.py`
- `add_home_value.py`
- `analyze_assets.py` (updates)
- `MORTGAGE_ARCHITECTURE.md` (design document)

---

## Loan Liability Tracking (Student Loans, Auto Loans, etc.)
**Priority:** Medium  
**Status:** Backlog

**Problem:**
Loan payments (student loans, auto loans, etc.) are currently treated as simple expense transactions (`Liabilities:Loans`, `Liabilities:StudentLoans`), which incorrectly sum payment aggregates rather than tracking actual outstanding principal balances from statements.

**Current State:**
- `Liabilities:Loans` and `Liabilities:StudentLoans` are displayed as $0.00 placeholders in `analyze_assets.py`.
- Old payment aggregates are excluded from calculations.
- Similar to the mortgage issue that was resolved.

**Proposed Solution:**
1. **Loan Statement Processing:**
   - Develop processors similar to `mortgage_processor.py` for each loan type.
   - Extract outstanding principal balance, interest rate, maturity date, payment breakdown.
   - Support PDF/text extraction with OCR fallback.
   - Create CSV templates for manual entry as fallbacks.
2. **Ledger Structure:**
   - `Liabilities:StudentLoans:Institution`: Track outstanding principal balance (from statements).
   - `Liabilities:AutoLoan:Institution`: Track outstanding principal balance (from statements).
   - `Liabilities:Loans:Institution`: Generic loan liability (if needed).
   - `Expenses:Interest:StudentLoans`: Interest portion of payments.
   - `Expenses:Interest:AutoLoan`: Interest portion of payments.
3. **Implementation:**
   - Create `finance_app/agents/ledger/loan_processor.py` (generic) or separate processors per loan type.
   - Create `add_loans_to_ledger.py` script to add loan balances to the ledger.
   - Update `analyze_assets.py` to:
     - Remove placeholder $0.00 entries.
     - Display actual statement-based loan balances.
     - Include loans in total liabilities calculation.

**Files (to be created):**
- `finance_app/agents/ledger/loan_processor.py` (or loan-specific processors)
- `add_loans_to_ledger.py`
- `analyze_assets.py` (updates)

---

## Cash Asset Balance Tracking
**Priority:** High  
**Status:** Backlog (Placeholder $0.00)

**Problem:**
Cash account balances (checking, savings) are currently showing incorrect negative balances (e.g., -$155,716.59 for checking) when actual balances are positive (e.g., ~$1,800). The ledger tracks transaction flows from 2021-2025 but lacks opening balances, so summing all transactions gives incorrect results.

**Current State:**
- Cash accounts are displayed as $0.00 placeholders in `analyze_assets.py`.
- Actual calculated balances are excluded because they're incorrect (missing opening balances).
- Similar to the loan liability issue - need statement-based balances.

**Root Cause:**
- Ledger starts from first transaction date (2021-01-08) with no opening balance entry.
- All entries are net changes (transactions), not absolute balances.
- Without an opening balance, summing transactions gives incorrect results.

**Proposed Solution:**
1. **Opening Balance Entries:**
   - Add opening balance entries for each cash account at the start of the ledger period.
   - Extract opening balances from earliest available statements.
   - Create ledger entries: `Assets:BankOfAmerica:Checking` with opening balance amount.

2. **Current Balance Snapshots (Alternative):**
   - Periodically add current balance snapshots from statements.
   - Use most recent snapshot as the "current" balance.
   - Update snapshots monthly/quarterly as statements arrive.

3. **Implementation:**
   - Create `add_opening_balances.py` script to add opening balances from CSV or statements.
   - Or modify `build_ledger.py` to accept opening balance CSV.
   - Update `analyze_assets.py` to:
     - Remove placeholder $0.00 entries.
     - Display actual balances (opening balance + transaction sum, or latest snapshot).

**Files (to be created/updated):**
- `add_opening_balances.py` (or integrate into `build_ledger.py`)
- `analyze_assets.py` (updates to remove placeholders)
- Opening balance CSV template (if manual entry needed)

---

## Future Items

_Additional backlog items will be added here as they are identified._

