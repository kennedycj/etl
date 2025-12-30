"""CD (Certificate of Deposit) processing utilities.

CDs are special: they don't have transaction feeds, but they're important assets
that need to be tracked for net worth, ladder strategy, and tax purposes.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json
import re


def extract_cd_info_from_pdf_filename(filename: str) -> Dict:
    """Extract CD information from PDF filename.
    
    Expected formats:
    - 2023-07-25_opening.pdf
    - 2024-12-03_renewal.pdf
    - 2026-07-03_maturity.pdf
    - cd_0534_7mo_featured_2024-12-03.pdf
    
    Returns:
        Dictionary with extracted metadata
    """
    metadata = {
        'filename': filename,
        'event_type': None,
        'date': None
    }
    
    # Try to extract date and event type from filename
    # Format: YYYY-MM-DD_eventtype.pdf
    match = re.match(r'(\d{4}-\d{2}-\d{2})_(.+)\.pdf', filename)
    if match:
        date_str = match.group(1)
        event_type = match.group(2)
        try:
            metadata['date'] = datetime.strptime(date_str, '%Y-%m-%d').isoformat()
            metadata['event_type'] = event_type
        except ValueError:
            pass
    
    # Alternative format: cd_XXXX_description_YYYY-MM-DD.pdf
    match = re.match(r'cd_(\d+)_(.+)_(\d{4}-\d{2}-\d{2})\.pdf', filename, re.IGNORECASE)
    if match and not metadata['date']:
        cd_id = match.group(1)
        description = match.group(2)
        date_str = match.group(3)
        try:
            metadata['date'] = datetime.strptime(date_str, '%Y-%m-%d').isoformat()
            metadata['cd_id'] = cd_id
            metadata['description'] = description
        except ValueError:
            pass
    
    return metadata


def infer_cd_structure_from_path(file_path: Path, raw_root: Path) -> Dict:
    """Infer CD metadata from file path structure.
    
    Expected structure: 00_raw/cds/{institution}/{cd_identifier}/{filename}
    Example: 00_raw/cds/bank_of_america/cd_0534_7mo_featured/2024-12-03_renewal.pdf
    
    Returns:
        Dictionary with inferred metadata
    """
    relative_path = file_path.relative_to(raw_root)
    parts = relative_path.parts
    
    metadata = {
        'relative_path': str(relative_path),
        'filename': file_path.name,
        'file_type': 'pdf'
    }
    
    # Parse structure: cds/institution/cd_identifier/filename
    if len(parts) >= 2 and parts[0] == 'cds':
        metadata['category'] = 'cds'
        metadata['institution'] = parts[1] if len(parts) > 1 else None
        metadata['cd_identifier'] = parts[2] if len(parts) > 2 else None
    
    # Extract info from filename
    filename_info = extract_cd_info_from_pdf_filename(file_path.name)
    metadata.update(filename_info)
    
    return metadata


def create_cd_snapshot_template() -> Dict:
    """Create template for CD snapshot record.
    
    Returns:
        Dictionary template for CD snapshot CSV row
    """
    return {
        'date': None,
        'cd_id': None,
        'balance': None,
        'interest_accrued': None,
        'interest_paid_ytd': None,
        'interest_withheld_this_year': None,
        'next_maturity_date': None,
        'source_pdf': None
    }


def create_cd_registry_template() -> Dict:
    """Create template for CD registry record.
    
    Returns:
        Dictionary template for CD registry CSV row
    """
    return {
        'cd_id': None,
        'institution': None,
        'account_number_masked': None,
        'nickname': None,
        'term_months': None,
        'open_date': None,
        'interest_rate': None,
        'apy': None,
        'principal': None,
        'linked_account': None
    }


def create_cd_cashflow_template() -> Dict:
    """Create template for CD cashflow record.
    
    Returns:
        Dictionary template for CD cashflow CSV row
    """
    return {
        'date': None,
        'cd_id': None,
        'amount': None,
        'flow_type': None,  # interest_payment, maturity_principal, renewal, opening
        'linked_account': None,
        'source_pdf': None
    }


def get_cd_normalized_path(archive_root: Path) -> Path:
    """Get path to normalized CD data directory.
    
    Returns:
        Path to 10_normalized/cds/ directory
    """
    return archive_root / "10_normalized" / "cds"


def ensure_cd_structure_exists(archive_root: Path):
    """Ensure CD directory structure exists."""
    # Raw structure
    (archive_root / "00_raw" / "cds").mkdir(parents=True, exist_ok=True)
    
    # Normalized structure
    normalized_path = get_cd_normalized_path(archive_root)
    normalized_path.mkdir(parents=True, exist_ok=True)


# Note: PDF text extraction would require additional libraries like pdfplumber or PyPDF2
# For now, this provides the structure. PDF parsing can be added later.
def parse_cd_pdf_content(pdf_path: Path) -> Dict:
    """Parse CD PDF content to extract structured data.
    
    This is a placeholder - actual PDF parsing requires pdfplumber or similar.
    
    Expected PDF format (based on user's example):
    - Nickname
    - Account number
    - Current balance
    - Date opened
    - Term
    - Next maturity date
    - Beginning balance this term
    - Last renewal date
    - Interest rate
    - Annual percentage yield
    - Interest earned not paid
    - Interest paid last year
    - Interest withheld for taxes
    
    Returns:
        Dictionary with extracted CD data
    """
    # TODO: Implement PDF parsing
    # For now, return structure template
    return {
        'nickname': None,
        'account_number': None,
        'current_balance': None,
        'date_opened': None,
        'term_months': None,
        'next_maturity_date': None,
        'beginning_balance': None,
        'last_renewal_date': None,
        'interest_rate': None,
        'apy': None,
        'interest_accrued': None,
        'interest_paid_last_year': None,
        'interest_withheld_this_year': None,
        'interest_withheld_last_year': None
    }

