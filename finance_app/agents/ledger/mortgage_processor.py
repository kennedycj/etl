"""Process US Bank mortgage statements to extract balance and payment information."""

import re
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, List
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


def extract_mortgage_data_from_pdf(pdf_path: Path) -> Optional[Dict]:
    """Extract mortgage balance and payment information from US Bank mortgage statement PDF.
    
    Args:
        pdf_path: Path to mortgage statement PDF
        
    Returns:
        Dictionary with mortgage data, or None if extraction fails
    """
    if not PDFPLUMBER_AVAILABLE:
        print("pdfplumber not available. Install with: pip install pdfplumber")
        return None
    
    if not pdf_path.exists():
        print(f"PDF file not found: {pdf_path}")
        return None
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
            
            # If no text extracted, try OCR
            if not full_text or len(full_text.strip()) < 10:
                print(f"Text extraction failed for {pdf_path.name}, trying OCR...")
                ocr_text = extract_text_with_ocr(pdf_path)
                if ocr_text:
                    full_text = ocr_text
                else:
                    print(f"OCR failed for {pdf_path}: No text extracted.")
                    print(f"  Note: This may be an image-based PDF requiring OCR.")
                    print(f"  Install Poppler from: https://github.com/oschwartz10612/poppler-windows/releases")
                    return None
            
            if not full_text or len(full_text.strip()) < 10:
                return None
            
            # Extract key information using regex patterns
            
            # Outstanding principal balance
            balance_patterns = [
                r'unpaid\s+principal\s+balance[:\s]*\$?([\d,]+\.?\d*)',
                r'principal\s+balance[:\s]*\$?([\d,]+\.?\d*)',
                r'outstanding\s+balance[:\s]*\$?([\d,]+\.?\d*)',
                r'balance\s+due[:\s]*\$?([\d,]+\.?\d*)',
                r'current\s+balance[:\s]*\$?([\d,]+\.?\d*)',
            ]
            principal_balance = None
            for pattern in balance_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    principal_balance = float(match.group(1).replace(',', ''))
                    break
            
            # Interest rate
            rate_patterns = [
                r'interest\s+rate[:\s]*([\d.]+)\s*%',
                r'rate[:\s]*([\d.]+)\s*%',
                r'(\d+\.\d+)\s*%\s*interest',
            ]
            interest_rate = None
            for pattern in rate_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    interest_rate = float(match.group(1)) / 100  # Convert to decimal
                    break
            
            # Maturity date
            maturity_patterns = [
                r'maturity\s+date[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'final\s+payment\s+date[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'loan\s+matures[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            ]
            maturity_date = None
            for pattern in maturity_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    date_str = match.group(1)
                    try:
                        # Try different date formats
                        for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y']:
                            try:
                                maturity_date = datetime.strptime(date_str, fmt)
                                break
                            except ValueError:
                                continue
                    except:
                        pass
                    break
            
            # Payment breakdown (principal, interest, escrow)
            # Look for payment breakdown table or summary
            principal_payment = None
            interest_payment = None
            escrow_payment = None
            total_payment = None
            
            # Try to find payment breakdown section
            payment_patterns = [
                r'principal[:\s]*\$?([\d,]+\.?\d*)',
                r'interest[:\s]*\$?([\d,]+\.?\d*)',
                r'escrow[:\s]*\$?([\d,]+\.?\d*)',
                r'total\s+payment[:\s]*\$?([\d,]+\.?\d*)',
            ]
            
            # Look for table with payment breakdown
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        table_text = "\n".join([" ".join(str(cell) if cell else "" for cell in row) for row in table])
                        # Check if this looks like a payment breakdown table
                        if 'principal' in table_text.lower() or 'interest' in table_text.lower():
                            # Try to extract values from table
                            for row in table:
                                row_text = " ".join(str(cell) if cell else "" for cell in row).lower()
                                if 'principal' in row_text:
                                    # Find number in this row
                                    nums = re.findall(r'[\d,]+\.?\d*', " ".join(str(cell) if cell else "" for cell in row))
                                    if nums:
                                        principal_payment = float(nums[0].replace(',', ''))
                                if 'interest' in row_text:
                                    nums = re.findall(r'[\d,]+\.?\d*', " ".join(str(cell) if cell else "" for cell in row))
                                    if nums:
                                        interest_payment = float(nums[0].replace(',', ''))
                                if 'escrow' in row_text:
                                    nums = re.findall(r'[\d,]+\.?\d*', " ".join(str(cell) if cell else "" for cell in row))
                                    if nums:
                                        escrow_payment = float(nums[0].replace(',', ''))
            
            # If not found in tables, try text patterns
            if not principal_payment:
                match = re.search(r'principal[:\s]*\$?([\d,]+\.?\d*)', full_text, re.IGNORECASE)
                if match:
                    principal_payment = float(match.group(1).replace(',', ''))
            
            if not interest_payment:
                match = re.search(r'interest[:\s]*\$?([\d,]+\.?\d*)', full_text, re.IGNORECASE)
                if match:
                    interest_payment = float(match.group(1).replace(',', ''))
            
            if not escrow_payment:
                match = re.search(r'escrow[:\s]*\$?([\d,]+\.?\d*)', full_text, re.IGNORECASE)
                if match:
                    escrow_payment = float(match.group(1).replace(',', ''))
            
            if not total_payment:
                match = re.search(r'total\s+payment[:\s]*\$?([\d,]+\.?\d*)', full_text, re.IGNORECASE)
                if match:
                    total_payment = float(match.group(1).replace(',', ''))
            
            # Statement date (usually on first page)
            statement_date = None
            date_patterns = [
                r'statement\s+date[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'as\s+of[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            ]
            for pattern in date_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    date_str = match.group(1)
                    try:
                        for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y']:
                            try:
                                statement_date = datetime.strptime(date_str, fmt)
                                break
                            except ValueError:
                                continue
                    except:
                        pass
                    break
            
            # If no statement date found, use PDF modification time or current date
            if not statement_date:
                statement_date = datetime.fromtimestamp(pdf_path.stat().st_mtime)
            
            result = {
                'statement_date': statement_date,
                'principal_balance': principal_balance,
                'interest_rate': interest_rate,
                'maturity_date': maturity_date,
                'principal_payment': principal_payment,
                'interest_payment': interest_payment,
                'escrow_payment': escrow_payment,
                'total_payment': total_payment,
                'raw_text': full_text[:1000]  # First 1000 chars for debugging
            }
            
            # Check if we got at least the principal balance
            if principal_balance is None:
                print(f"Warning: Could not extract principal balance from {pdf_path.name}")
                print("Extracted text preview:")
                print(full_text[:500])
                return None
            
            return result
            
    except Exception as e:
        print(f"Error parsing mortgage PDF {pdf_path}: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_mortgage_csv_template(mortgage_directory: Path) -> Path:
    """Create a CSV template for manual mortgage data entry.
    
    Args:
        mortgage_directory: Directory containing mortgage PDF files
        
    Returns:
        Path to created CSV template
    """
    csv_path = mortgage_directory / "mortgage_balance.csv"
    
    template_data = {
        'statement_date': [],
        'principal_balance': [],
        'interest_rate': [],
        'maturity_date': [],
        'notes': []
    }
    
    template_df = pd.DataFrame(template_data)
    template_df.to_csv(csv_path, index=False)
    
    return csv_path


def load_mortgage_balance_from_csv(csv_path: Path) -> Optional[Dict]:
    """Load mortgage balance from manually created CSV.
    
    Expected CSV format:
    - statement_date: Statement date (YYYY-MM-DD)
    - principal_balance: Outstanding principal balance
    - interest_rate: Interest rate as decimal (e.g., 0.0425 for 4.25%)
    - maturity_date: Loan maturity date (YYYY-MM-DD, optional)
    - notes: Optional notes
    
    Args:
        csv_path: Path to mortgage balance CSV
        
    Returns:
        Dictionary with mortgage data, or None if file doesn't exist
    """
    if not csv_path.exists():
        return None
    
    df = pd.read_csv(csv_path)
    
    # Get the most recent entry (if multiple)
    if len(df) == 0:
        return None
    
    # Sort by date and take most recent
    df['statement_date'] = pd.to_datetime(df['statement_date'])
    df = df.sort_values('statement_date', ascending=False)
    
    row = df.iloc[0]
    
    return {
        'statement_date': row['statement_date'],
        'principal_balance': float(row['principal_balance']),
        'interest_rate': float(row['interest_rate']) if pd.notna(row.get('interest_rate')) else None,
        'maturity_date': pd.to_datetime(row['maturity_date']).to_pydatetime() if pd.notna(row.get('maturity_date')) else None,
        'notes': row.get('notes', '')
    }


def create_mortgage_ledger_entry(mortgage_data: Dict, institution: str = "USBank",
                                 mortgage_account: str = "Liabilities:Mortgage:USBank") -> Dict:
    """Create a ledger entry for mortgage balance.
    
    Creates a balance update entry showing the current principal balance.
    This is a liability, so negative balance means you owe money.
    
    Args:
        mortgage_data: Dictionary with mortgage data (from extract or CSV)
        institution: Institution name
        mortgage_account: Ledger account path for mortgage
        
    Returns:
        Dictionary with ledger entry information
    """
    statement_date = mortgage_data['statement_date']
    if isinstance(statement_date, datetime):
        date_str = statement_date.strftime('%Y-%m-%d')
    else:
        date_str = str(statement_date)
    
    principal_balance = Decimal(str(mortgage_data['principal_balance']))
    
    description = f"Mortgage balance as of {date_str}"
    if mortgage_data.get('interest_rate'):
        rate_pct = float(mortgage_data['interest_rate']) * 100
        description += f" (rate: {rate_pct:.2f}%)"
    
    # For liability account, negative balance means you owe money
    # So we represent the principal balance as negative
    return {
        'date': date_str,
        'description': description,
        'account': mortgage_account,
        'amount': float(-principal_balance),  # Negative because it's a liability
        'source_file': f'mortgage/{institution.lower()}/statement_{date_str}'
    }

