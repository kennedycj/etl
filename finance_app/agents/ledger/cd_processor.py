"""CD (Certificate of Deposit) processing for ledger integration.

Handles:
- PDF parsing to extract CD balances and metadata
- Finding latest CD statement per account
- Matching CD transactions to checking account transactions
- Creating ledger entries for CDs
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


def parse_cd_filename(filename: str) -> Optional[Dict]:
    """Parse CD filename to extract account number and date range.
    
    Format: {last4}_YYYY_MM_DD_to_YYYY_MM_DD.pdf
    Example: 0534_2025_03_12_to_2026_07_03.pdf
    
    Returns:
        Dictionary with cd_id (last4), start_date, end_date, or None if invalid
    """
    match = re.match(r'^(\d{4})_(\d{4})_(\d{2})_(\d{2})_to_(\d{4})_(\d{2})_(\d{2})\.pdf$', filename)
    if not match:
        return None
    
    cd_id = match.group(1)  # Last 4 digits
    start_date = datetime(int(match.group(2)), int(match.group(3)), int(match.group(4)))
    end_date = datetime(int(match.group(5)), int(match.group(6)), int(match.group(7)))
    
    return {
        'cd_id': cd_id,
        'start_date': start_date,
        'end_date': end_date,
        'filename': filename
    }


def extract_text_with_ocr(pdf_path: Path) -> Optional[str]:
    """Extract text from PDF using OCR as fallback.
    
    Requires:
    - Tesseract OCR installed (https://github.com/tesseract-ocr/tesseract)
    - Poppler utils installed (for pdf2image)
      - Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases
      - Add to PATH or set POPPLER_PATH environment variable
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Extracted text string, or None if OCR fails
    """
    if not OCR_AVAILABLE:
        return None
    
    try:
        # Convert PDF pages to images
        # Try with poppler path if available
        import os
        poppler_path = os.environ.get('POPPLER_PATH')
        if poppler_path:
            images = convert_from_path(str(pdf_path), dpi=300, poppler_path=poppler_path)
        else:
            images = convert_from_path(str(pdf_path), dpi=300)
        
        # Extract text from each page using OCR
        full_text = ""
        for image in images:
            text = pytesseract.image_to_string(image)
            if text:
                full_text += text + "\n"
        
        return full_text if full_text.strip() else None
    except Exception as e:
        error_msg = str(e)
        if "poppler" in error_msg.lower() or "Unable to get page count" in error_msg:
            print(f"  Note: Poppler is required for OCR. Install from:")
            print(f"  https://github.com/oschwartz10612/poppler-windows/releases")
            print(f"  Then add to PATH or set POPPLER_PATH environment variable")
        elif "tesseract" in error_msg.lower():
            print(f"  Note: Tesseract OCR is required. Install from:")
            print(f"  https://github.com/tesseract-ocr/tesseract")
            print(f"  Then add to PATH")
        else:
            print(f"  OCR error: {error_msg}")
        return None


def extract_cd_balance_from_pdf(pdf_path: Path, use_ocr: bool = True) -> Optional[Dict]:
    """Extract CD balance and metadata from Bank of America CD statement PDF.
    
    Expected PDF format (based on user's example):
    - Current balance: $XX,XXX.XX
    - Account number
    - Date opened
    - Term
    - Next maturity date
    - Interest rate, APY
    - Interest amounts
    
    Returns:
        Dictionary with extracted CD data, or None if parsing fails
    """
    if not PDFPLUMBER_AVAILABLE:
        raise ImportError("pdfplumber is required for PDF parsing. Install with: pip install pdfplumber")
    
    if not pdf_path.exists():
        return None
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Extract text from all pages
            full_text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
            
            # If no text extracted, try extracting tables
            if not full_text:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        if table:
                            full_text += "\n".join([" ".join(str(cell) if cell else "" for cell in row) for row in table]) + "\n"
            
            # If no text extracted and OCR is available, try OCR
            if (not full_text or len(full_text.strip()) < 10) and OCR_AVAILABLE:
                print(f"Text extraction failed for {pdf_path.name}, trying OCR...")
                ocr_text = extract_text_with_ocr(pdf_path)
                if ocr_text:
                    full_text = ocr_text
            
            if not full_text or len(full_text.strip()) < 10:
                return None
            
            # Parse current balance
            # Look for patterns like "Current balance:$20,000.00" or "Current balance: $20,000.00"
            balance_match = re.search(r'Current balance\s*:\s*\$?([\d,]+\.\d{2})', full_text, re.IGNORECASE)
            current_balance = None
            if balance_match:
                current_balance = Decimal(balance_match.group(1).replace(',', ''))
            
            # Parse account number (usually shown as "Account number:" or "Show Account number")
            account_match = re.search(r'Account number\s*:?\s*(\d{4,})', full_text, re.IGNORECASE)
            account_number = None
            if account_match:
                account_number = account_match.group(1)
            
            # Parse date opened
            date_opened = None
            date_match = re.search(r'Date opened\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})', full_text, re.IGNORECASE)
            if date_match:
                try:
                    date_opened = datetime.strptime(date_match.group(1), '%m/%d/%Y')
                except ValueError:
                    pass
            
            # Parse next maturity date
            maturity_match = re.search(r'Next maturity date\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})', full_text, re.IGNORECASE)
            next_maturity = None
            if maturity_match:
                try:
                    next_maturity = datetime.strptime(maturity_match.group(1), '%m/%d/%Y')
                except ValueError:
                    pass
            
            # Parse interest rate
            rate_match = re.search(r'Interest rate\s*:?\s*([\d.]+)%', full_text, re.IGNORECASE)
            interest_rate = None
            if rate_match:
                try:
                    interest_rate = Decimal(rate_match.group(1)) / 100
                except:
                    pass
            
            # Parse APY
            apy_match = re.search(r'Annual percentage yield\s*:?\s*([\d.]+)%', full_text, re.IGNORECASE)
            apy = None
            if apy_match:
                try:
                    apy = Decimal(apy_match.group(1)) / 100
                except:
                    pass
            
            # Parse interest earned not paid
            accrued_match = re.search(r'Interest earned not paid\s*:?\s*\$?([\d,]+\.\d{2})', full_text, re.IGNORECASE)
            interest_accrued = None
            if accrued_match:
                interest_accrued = Decimal(accrued_match.group(1).replace(',', ''))
            
            return {
                'current_balance': current_balance,
                'account_number': account_number,
                'date_opened': date_opened,
                'next_maturity_date': next_maturity,
                'interest_rate': interest_rate,
                'apy': apy,
                'interest_accrued': interest_accrued,
                'raw_text': full_text  # Keep for debugging
            }
    
    except Exception as e:
        print(f"Error parsing PDF {pdf_path}: {e}")
        return None


def find_latest_cd_statements(cd_directory: Path) -> Dict[str, Path]:
    """Find the latest CD statement PDF per account number.
    
    Args:
        cd_directory: Directory containing CD PDF files
        
    Returns:
        Dictionary mapping cd_id (last 4 digits) to Path of latest PDF
    """
    if not cd_directory.exists():
        return {}
    
    cd_files: Dict[str, Tuple[Path, datetime]] = {}
    
    for pdf_file in cd_directory.glob('*.pdf'):
        parsed = parse_cd_filename(pdf_file.name)
        if not parsed:
            continue
        
        cd_id = parsed['cd_id']
        end_date = parsed['end_date']
        
        # Keep the file with the latest end_date for each cd_id
        if cd_id not in cd_files or end_date > cd_files[cd_id][1]:
            cd_files[cd_id] = (pdf_file, end_date)
    
    return {cd_id: path for cd_id, (path, _) in cd_files.items()}


def load_cd_balances(cd_directory: Path, institution: str = "BankOfAmerica") -> pd.DataFrame:
    """Load CD balances from latest statements.
    
    Args:
        cd_directory: Directory containing CD PDF files
        institution: Institution name
        
    Returns:
        DataFrame with columns: cd_id, institution, account_number, balance, 
        next_maturity_date, interest_rate, apy, interest_accrued, statement_date
    """
    latest_statements = find_latest_cd_statements(cd_directory)
    
    cd_records = []
    for cd_id, pdf_path in latest_statements.items():
        parsed_info = extract_cd_balance_from_pdf(pdf_path)
        filename_info = parse_cd_filename(pdf_path.name)
        
        if not parsed_info or not filename_info:
            continue
        
        record = {
            'cd_id': cd_id,
            'institution': institution,
            'account_number': parsed_info.get('account_number') or cd_id,
            'balance': float(parsed_info.get('current_balance', 0)),
            'next_maturity_date': parsed_info.get('next_maturity_date'),
            'interest_rate': float(parsed_info.get('interest_rate', 0)) if parsed_info.get('interest_rate') else None,
            'apy': float(parsed_info.get('apy', 0)) if parsed_info.get('apy') else None,
            'interest_accrued': float(parsed_info.get('interest_accrued', 0)) if parsed_info.get('interest_accrued') else None,
            'statement_date': filename_info['end_date'],
            'pdf_path': str(pdf_path)
        }
        cd_records.append(record)
    
    return pd.DataFrame(cd_records)


def find_cd_transactions_in_ledger(ledger_df: pd.DataFrame, cd_id: str) -> pd.DataFrame:
    """Find transactions related to a specific CD in the ledger.
    
    Looks for transactions with descriptions containing:
    - "CD {cd_id}"
    - "transfer from CD {cd_id}"
    - "transfer to CD {cd_id}"
    - Account names containing CD
    
    Args:
        ledger_df: DataFrame with ledger entries
        cd_id: CD account number (last 4 digits)
        
    Returns:
        DataFrame with matching transactions
    """
    # Normalize descriptions for searching
    descriptions = ledger_df['description'].fillna('').astype(str).str.lower()
    accounts = ledger_df['account'].fillna('').astype(str).str.lower()
    
    # Search patterns
    cd_patterns = [
        f'cd {cd_id}',
        f'cd{cd_id}',
        f'transfer from cd {cd_id}',
        f'transfer to cd {cd_id}',
        f'agent assisted transfer.*cd {cd_id}',
    ]
    
    matches = pd.Series([False] * len(ledger_df))
    for pattern in cd_patterns:
        matches |= descriptions.str.contains(pattern, regex=True, na=False)
    
    # Also check account names
    matches |= accounts.str.contains(f'cd.*{cd_id}', regex=True, na=False, case=False)
    
    return ledger_df[matches].copy()


def create_cd_ledger_entries(cd_df: pd.DataFrame, statement_date: datetime, 
                              institution: str = "BankOfAmerica") -> List[Tuple[str, str, Decimal, datetime, str]]:
    """Create ledger entries for CD balances.
    
    Creates entries as opening balances or current balances for asset accounts.
    Format: (date, description, account, amount, source_file)
    
    Args:
        cd_df: DataFrame with CD data (from load_cd_balances)
        statement_date: Date for the ledger entries (use latest statement date or current date)
        institution: Institution name
        
    Returns:
        List of tuples: (date_str, description, account, amount, source_file)
    """
    entries = []
    
    for _, row in cd_df.iterrows():
        cd_id = row['cd_id']
        balance = Decimal(str(row['balance']))
        account = f"Assets:BankOfAmerica:CD:{cd_id}"
        description = f"CD {cd_id} balance as of {statement_date.strftime('%Y-%m-%d')}"
        source_file = row.get('pdf_path', f'cds/bank_of_america/{cd_id}')
        
        entries.append((
            statement_date.strftime('%Y-%m-%d'),
            description,
            account,
            balance,  # Assets are positive
            source_file
        ))
    
    return entries


def match_cd_transactions(ledger_df: pd.DataFrame, max_days_diff: int = 7) -> List[Dict]:
    """Match CD transactions in the ledger (withdrawals, maturities, interest payments).
    
    Looks for transactions like:
    - "Agent Assisted transfer from CD {cd_id}" 
    - "Agent Assisted transfer to CD {cd_id}"
    - CD-related transfers
    
    Args:
        ledger_df: DataFrame with ledger entries
        max_days_diff: Maximum days difference for matching
        
    Returns:
        List of matched transaction dictionaries
    """
    matches = []
    
    # Find all CD-related transactions
    cd_patterns = [
        r'cd\s+\d{4}',
        r'agent\s+assisted\s+transfer.*cd',
        r'transfer.*cd\s+\d{4}',
    ]
    
    cd_transactions = pd.DataFrame()
    for pattern in cd_patterns:
        mask = ledger_df['description'].fillna('').str.lower().str.contains(pattern, regex=True, na=False)
        cd_transactions = pd.concat([cd_transactions, ledger_df[mask]])
    
    cd_transactions = cd_transactions.drop_duplicates()
    
    # Group by CD ID and date to find matching pairs
    for _, cd_row in cd_transactions.iterrows():
        desc = str(cd_row['description']).lower()
        
        # Extract CD ID from description
        cd_id_match = re.search(r'cd\s*(\d{4})', desc, re.IGNORECASE)
        if not cd_id_match:
            continue
        
        cd_id = cd_id_match.group(1)
        cd_date = pd.to_datetime(cd_row['date'])
        cd_amount = abs(float(cd_row['amount']))
        
        # Look for matching checking account transaction
        checking_mask = (
            (ledger_df['account'].str.startswith('Assets:', na=False)) &
            (ledger_df['account'].str.contains('Checking', case=False, na=False))
        )
        
        checking_transactions = ledger_df[checking_mask].copy()
        checking_transactions['date'] = pd.to_datetime(checking_transactions['date'])
        checking_transactions['amount'] = pd.to_numeric(checking_transactions['amount'], errors='coerce')
        
        # Find matches by amount and date
        date_diff = abs((checking_transactions['date'] - cd_date).dt.days)
        amount_diff = abs(abs(checking_transactions['amount']) - cd_amount)
        
        potential_matches = checking_transactions[
            (date_diff <= max_days_diff) & (amount_diff < 0.01)
        ]
        
        if len(potential_matches) > 0:
            match_row = potential_matches.iloc[0]
            matches.append({
                'cd_id': cd_id,
                'cd_entry': cd_row.to_dict(),
                'checking_entry': match_row.to_dict(),
                'date': cd_date,
                'amount': cd_amount,
                'confidence': 1.0 if date_diff.iloc[0] == 0 and amount_diff.iloc[0] < 0.01 else 0.8
            })
    
    return matches


