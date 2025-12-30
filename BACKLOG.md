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

## Future Items

_Additional backlog items will be added here as they are identified._

