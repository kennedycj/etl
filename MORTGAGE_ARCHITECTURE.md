# Mortgage & Home Equity Architecture

## Current State

Mortgage payments are currently tracked as simple liability payments:
- `Liabilities:Mortgage:USBank` - Total payment amount (incorrect)

**Problems:**
1. Payments include principal + interest + escrow, but all treated as liability reduction
2. No breakdown of payment components
3. Balance is inferred from payments, not from actual statements
4. No home value tracking
5. No equity calculation

## Proposed Solution

### 1. Mortgage Statement Processing

Similar to HELOC/CD processing, create a mortgage statement processor:

**Location**: `finance_app/agents/ledger/mortgage_processor.py`

**Archive Structure**:
```
00_raw/
└── bank/
    └── us_bank/
        └── mortgage/
            ├── 2024_01_01_statement.pdf
            ├── 2024_02_01_statement.pdf
            └── ...
```

**Data Structure** (per statement):
```python
{
    'statement_date': '2025-12-01',
    'beginning_balance': 450000.00,  # Principal at start of period
    'ending_balance': 448000.00,      # Principal at end of period
    'principal_payment': 1000.00,     # Principal paid this period
    'interest_payment': 1800.00,      # Interest paid this period
    'escrow_payment': 967.43,         # Escrow (taxes + insurance) paid
    'total_payment': 3767.43,         # Total payment made
    'interest_rate': 0.0425,          # Current interest rate
    'next_payment_due': '2026-01-01',
    'escrow_balance': 5000.00,        # Current escrow balance
    'source_file': 'mortgage/us_bank/statement_2025_12.pdf'
}
```

### 2. Ledger Account Structure

**Liabilities:**
- `Liabilities:Mortgage:USBank` - Outstanding principal balance (from statements)

**Expenses:**
- `Expenses:Interest:Mortgage` - Interest payments (expense)
- `Expenses:Taxes:Property` - Property tax portion of escrow
- `Expenses:Insurance:Home` - Home insurance portion of escrow (optional, if breakdown available)

**Assets:**
- `Assets:RealEstate:PrimaryResidence` - Home value (manual entry, updated periodically)
- `Assets:RealEstate:PrimaryResidence:Equity` - **Calculated**: Home Value - Mortgage Balance - HELOC Balance

### 3. Ledger Entry Strategy

**Option A: Balance Updates Only (Recommended for Start)**
- Track outstanding balance from statements
- Update liability balance periodically (monthly)
- Post interest and escrow as expenses separately

For each statement:
```
Date: statement_date
Description: Mortgage balance update (principal: $X, interest: $Y, escrow: $Z)
Liabilities:Mortgage:USBank: -principal_payment (reduces liability)
Expenses:Interest:Mortgage: +interest_payment (expense)
Expenses:Taxes:Property: +escrow_payment (expense)
Assets:BankOfAmerica:Checking: +total_payment (source of payment)
```

**Option B: Individual Payment Tracking**
- Track each payment transaction separately
- Requires payment breakdown from statements
- More granular but more complex

### 4. Home Value Tracking

**Manual Entry CSV**: `home_value.csv`
```
date,value,source,notes
2024-01-01,600000.00,Appraisal,Annual appraisal
2024-06-01,610000.00,Estimated,Market adjustment
2025-01-01,620000.00,Appraisal,Annual appraisal
```

**Equity Calculation** (in `analyze_assets.py`):
```python
home_value = get_latest_home_value()  # From CSV
mortgage_balance = calculate_liability_balance('Liabilities:Mortgage:USBank')
heloc_balance = calculate_liability_balance('Liabilities:HELOC:USBank')
equity = home_value - abs(mortgage_balance) - abs(heloc_balance)
```

### 5. Implementation Steps

1. **Create `mortgage_processor.py`**
   - PDF parsing for US Bank mortgage statements
   - CSV template for manual entry (fallback)
   - Extract: balance, principal, interest, escrow

2. **Create `add_mortgage_to_ledger.py` script**
   - Similar to `add_heloc_to_ledger.py`
   - Processes mortgage statements
   - Creates ledger entries with proper breakdown

3. **Update `analyze_assets.py`**
   - Add `analyze_real_estate()` function
   - Calculate equity: Home Value - Mortgage - HELOC
   - Display in assets summary

4. **Create `add_home_value.py` script** (optional)
   - Or integrate into mortgage processor
   - Track home value over time
   - Update equity calculations

5. **Update `rebuild_ledger.py`**
   - Include mortgage processing step
   - Include home value loading step

### 6. Data Flow

```
US Bank Mortgage Statements (PDFs)
    ↓
mortgage_processor.py (extract data)
    ↓
add_mortgage_to_ledger.py
    ↓
ledger_with_mortgage.csv (or ledger_with_heloc.csv → ledger_complete.csv)
    ↓
analyze_assets.py (includes equity calculation)
```

### 7. Considerations

**Statement Frequency:**
- Monthly statements preferred
- Use most recent statement for current balance
- Can interpolate between statements if gaps exist

**Payment Breakdown:**
- Most statements show: principal, interest, escrow
- Escrow may not be broken down (tax vs insurance)
- Start simple: treat total escrow as property tax expense

**Home Value Updates:**
- Annual appraisals (if available)
- Zillow/Redfin estimates (less reliable)
- Manual adjustments based on improvements
- Update frequency: Quarterly or annually

**Existing Payment Transactions:**
- Current mortgage payment transactions in ledger are incorrect
- Should remove old mortgage entries before adding statement-based entries
- Or: Keep payment transactions but reclassify them once statements are loaded

### 8. Questions for Implementation

1. Do you have US Bank mortgage statements available? (PDF format)
2. How often do you want to update home value? (Quarterly, annually, or manually)
3. Should we remove existing mortgage payment transactions, or keep them and override with statement data?
4. Do you want to track escrow breakdown (tax vs insurance), or just total escrow?

## Recommendation

**Phase 1 (Start Simple):**
1. Create mortgage processor with CSV manual entry
2. Track balance updates only (from statements)
3. Post interest and escrow as expenses
4. Add home value tracking (manual CSV)
5. Calculate equity in `analyze_assets.py`

**Phase 2 (Enhanced):**
1. Add PDF parsing for statements
2. Track individual payment breakdowns
3. Separate escrow into tax vs insurance
4. Add home value change tracking (unrealized gains/losses)
