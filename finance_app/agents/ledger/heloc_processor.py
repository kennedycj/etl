"""HELOC (Home Equity Line of Credit) processing for ledger integration.

HELOC accounts are liabilities - transactions affect the outstanding balance.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional
import re
import pandas as pd

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


def extract_text_with_ocr(pdf_path: Path) -> Optional[str]:
    """Extract text from PDF using OCR as fallback.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Extracted text string, or None if OCR fails
    """
    if not OCR_AVAILABLE:
        return None
    
    try:
        import os
        poppler_path = os.environ.get('POPPLER_PATH')
        if poppler_path:
            images = convert_from_path(str(pdf_path), dpi=300, poppler_path=poppler_path)
        else:
            images = convert_from_path(str(pdf_path), dpi=300)
        
        full_text = ""
        for image in images:
            text = pytesseract.image_to_string(image)
            if text:
                full_text += text + "\n"
        
        return full_text if full_text.strip() else None
    except Exception as e:
        error_msg = str(e)
        if "poppler" in error_msg.lower():
            print(f"  Note: Poppler required for OCR. Install from:")
            print(f"  https://github.com/oschwartz10612/poppler-windows/releases")
        return None


def extract_heloc_transactions_from_pdf(pdf_path: Path) -> List[Dict]:
    """Extract HELOC transactions from US Bank PDF statement.
    
    Expected format:
    - Date: MM/DD/YYYY
    - Description: "Advance", "Payment - Thank You", "Principal Payment", etc.
    - Amount: With $ sign, commas allowed
    
    Args:
        pdf_path: Path to HELOC statement PDF
        
    Returns:
        List of transaction dictionaries with date, description, amount
    """
    if not PDFPLUMBER_AVAILABLE:
        return []
    
    if not pdf_path.exists():
        return []
    
    transactions = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Extract transactions from tables (more reliable than text parsing)
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    
                    # Look for transaction tables (typically have date, description, amount columns)
                    for row in table:
                        if not row or len(row) < 2:
                            continue
                        
                        # Combine row cells into text
                        row_text = " ".join(str(cell) if cell else "" for cell in row).strip()
                        if not row_text:
                            continue
                        
                        # Look for transaction patterns
                        # Format: "MM/DD/YYYY Description $amount" or "MM/DD/YYYY Description $amount"
                        # Examples: "12/22/2025 Advance $12,815.46"
                        #          "12/18/2025 $ Principal Payment + $1,496.54"
                        
                        # Match date at start: MM/DD/YYYY or MM/DD/YY
                        date_match = re.search(r'^(\d{1,2}/\d{1,2}/\d{4}|\d{1,2}/\d{1,2}/\d{2})', row_text)
                        if not date_match:
                            continue
                        
                        date_str = date_match.group(1)
                        
                        # Parse date
                        try:
                            if len(date_str.split('/')[-1]) == 2:
                                # 2-digit year, assume 2000s
                                date = datetime.strptime(date_str, '%m/%d/%y')
                            else:
                                date = datetime.strptime(date_str, '%m/%d/%Y')
                        except ValueError:
                            continue
                        
                        # Extract amount (look for $XX,XXX.XX pattern)
                        amount_match = re.search(r'\$([\d,]+\.\d{2})', row_text)
                        if not amount_match:
                            continue
                        
                        amount_str = amount_match.group(1).replace(',', '')
                        try:
                            amount = Decimal(amount_str)
                        except:
                            continue
                        
                        # Extract description (between date and amount)
                        # Remove date and amount, clean up
                        desc = row_text.replace(date_str, '').strip()
                        desc = re.sub(r'\$\s*[\d,]+\.\d{2}', '', desc).strip()
                        desc = re.sub(r'\s+', ' ', desc)  # Normalize whitespace
                        
                        # Determine if it's a payment (negative) or advance/charge (positive)
                        # Advances/draws increase liability (positive amount)
                        # Payments decrease liability (negative amount)
                        if 'payment' in desc.lower() or 'thank you' in desc.lower():
                            amount = -abs(amount)  # Payments are negative
                        else:
                            amount = abs(amount)  # Advances/charges are positive
                        
                        transactions.append({
                            'date': date,
                            'description': desc,
                            'amount': float(amount)
                        })
            
            # If no transactions found in tables, try text parsing
            if not transactions:
                full_text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"
                
                # Parse transactions from text using regex
                # Pattern: "MM/DD/YYYY Description $amount"
                transaction_pattern = r'(\d{1,2}/\d{1,2}/\d{2,4})\s+([^$]+?)\s+\$([\d,]+\.\d{2})'
                matches = re.finditer(transaction_pattern, full_text)
                
                for match in matches:
                    date_str = match.group(1)
                    desc = match.group(2).strip()
                    amount_str = match.group(3).replace(',', '')
                    
                    try:
                        if len(date_str.split('/')[-1]) == 2:
                            date = datetime.strptime(date_str, '%m/%d/%y')
                        else:
                            date = datetime.strptime(date_str, '%m/%d/%Y')
                        
                        amount = Decimal(amount_str)
                        
                        # Determine sign based on description
                        if 'payment' in desc.lower() or 'thank you' in desc.lower():
                            amount = -abs(amount)
                        else:
                            amount = abs(amount)
                        
                        transactions.append({
                            'date': date,
                            'description': desc,
                            'amount': float(amount)
                        })
                    except:
                        continue
            
    except Exception as e:
        print(f"Error parsing HELOC PDF {pdf_path}: {e}")
        return []
    
    # Remove duplicates (same date, description, amount)
    seen = set()
    unique_transactions = []
    for tx in transactions:
        key = (tx['date'], tx['description'], tx['amount'])
        if key not in seen:
            seen.add(key)
            unique_transactions.append(tx)
    
    return unique_transactions


def create_heloc_csv_template(heloc_directory: Path) -> Path:
    """Create a CSV template for manual HELOC transaction entry.
    
    Args:
        heloc_directory: Directory containing HELOC PDF files
        
    Returns:
        Path to created CSV template
    """
    csv_path = heloc_directory / "heloc_transactions.csv"
    
    # Create template with standard transaction columns
    template_data = {
        'date': [],
        'description': [],
        'amount': [],  # Positive for charges/debits, negative for payments/credits
        'balance': []  # Optional - running balance
    }
    
    template_df = pd.DataFrame(template_data)
    template_df.to_csv(csv_path, index=False)
    
    return csv_path


def load_heloc_transactions_from_csv(csv_path: Path) -> pd.DataFrame:
    """Load HELOC transactions from manually created CSV.
    
    Expected CSV format:
    - date: Transaction date (YYYY-MM-DD or MM/DD/YYYY)
    - description: Transaction description
    - amount: Transaction amount (positive = charge/debit, negative = payment/credit)
    - balance: Optional running balance
    
    Args:
        csv_path: Path to HELOC transactions CSV
        
    Returns:
        DataFrame with HELOC transactions
    """
    if not csv_path.exists():
        return pd.DataFrame()
    
    df = pd.read_csv(csv_path)
    
    # Validate required columns
    required = ['date', 'description', 'amount']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    # Parse dates
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df[df['date'].notna()]  # Remove rows with invalid dates
    
    # Parse amounts
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    df = df[df['amount'].notna()]  # Remove rows with invalid amounts
    
    return df


def create_heloc_ledger_entries(transactions_df: pd.DataFrame, 
                                institution: str = "USBank",
                                heloc_account: str = "Liabilities:HELOC:USBank") -> List[Dict]:
    """Create ledger entries for HELOC transactions.
    
    HELOC transactions are liabilities:
    - Positive amounts (charges/draws) increase liability
    - Negative amounts (payments) decrease liability
    
    Args:
        transactions_df: DataFrame with HELOC transactions
        institution: Institution name
        heloc_account: Ledger account path for HELOC
        
    Returns:
        List of ledger entry dictionaries
    """
    entries = []
    
    for _, row in transactions_df.iterrows():
        date = row['date']
        description = str(row['description'])
        amount = Decimal(str(row['amount']))
        
        # For HELOC liability account:
        # - Advances = borrowing more = liability INCREASES = should be NEGATIVE in ledger
        # - Payments = paying down = liability DECREASES = should be POSITIVE in ledger
        # 
        # The CSV should already have the correct signs:
        # - Advances are negative (increases liability)
        # - Payments are positive (decreases liability)
        # 
        # In double-entry for liability:
        # Advance: HELOC liability increases (negative), asset/expense increases (positive)
        # Payment: HELOC liability decreases (positive), asset decreases (negative)
        
        # Use the amount directly - CSV should already have correct signs for liability account
        # If CSV has: advances as negative, payments as positive, use as-is
        # If CSV has: advances as positive, payments as negative, flip signs
        # We'll assume the CSV is already in the correct format (reconciled by user)
        liability_amount = float(amount)
        
        # Determine the offsetting account
        # For liability account: negative = advance (increases liability), positive = payment (decreases liability)
        if liability_amount < 0:  # Advance (increases liability)
            # HELOC liability increases (negative), determine based on description
            if 'transfer' in description.lower() or 'withdrawal' in description.lower() or 'advance' in description.lower():
                offset_account = "Assets:BankOfAmerica:Checking"  # Usually goes to checking
            else:
                offset_account = "Expenses:HELOC:Interest"  # Default to interest expense
            offset_amount = abs(liability_amount)  # Asset/expense increases (positive)
        else:  # Payment (decreases liability)
            # HELOC liability decreases (positive), checking asset decreases (negative)
            offset_account = "Assets:BankOfAmerica:Checking"  # Assuming payments from checking
            offset_amount = -abs(liability_amount)  # Asset decreases (negative)
        
        entries.append({
            'date': date.strftime('%Y-%m-%d') if isinstance(date, datetime) else str(date),
            'description': description,
            'account': heloc_account,
            'amount': float(liability_amount),  # Liability: advances negative, payments positive
            'offset_account': offset_account,
            'offset_amount': float(offset_amount),  # Opposite side
            'source_file': f'heloc/us_bank/{date.strftime("%Y%m") if isinstance(date, datetime) else "unknown"}.pdf'
        })
    
    return entries

