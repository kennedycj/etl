"""Data cleansing tools - normalize and clean transaction data."""

import csv
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
from dateutil import parser as date_parser

from finance_app.agents.data_curation.validation import detect_delimiter
from finance_app.agents.data_curation.ingestion import get_default_archive_root


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string in various formats.
    
    Args:
        date_str: Date string to parse
        
    Returns:
        Parsed datetime or None if parsing fails
    """
    if not date_str or not str(date_str).strip():
        return None
    
    date_str = str(date_str).strip()
    
    # Try common formats first
    formats = ["%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%Y/%m/%d", "%m/%d/%y"]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # Try dateutil parser
    try:
        return date_parser.parse(date_str)
    except:
        return None


def clean_amount(amount_str: str) -> Optional[Decimal]:
    """Clean and parse amount string.
    
    Handles:
    - Commas (1,234.56)
    - Dollar signs ($100.00)
    - Parentheses for negatives ((100.00) = -100.00)
    - Negative signs
    
    Args:
        amount_str: Amount string to clean
        
    Returns:
        Decimal amount or None if parsing fails
    """
    if not amount_str:
        return None
    
    amount_str = str(amount_str).strip()
    
    # Handle parentheses notation (negative)
    is_negative = False
    if amount_str.startswith('(') and amount_str.endswith(')'):
        amount_str = amount_str[1:-1]
        is_negative = True
    
    # Remove currency symbols and commas
    amount_str = amount_str.replace('$', '').replace(',', '').strip()
    
    # Check for negative sign
    if amount_str.startswith('-'):
        is_negative = True
        amount_str = amount_str[1:]
    
    try:
        amount = Decimal(amount_str)
        return -amount if is_negative else amount
    except (InvalidOperation, ValueError):
        return None


def normalize_description(description: str) -> str:
    """Normalize transaction description.
    
    Args:
        description: Original description
        
    Returns:
        Cleaned description
    """
    if not description:
        return ""
    
    # Remove extra whitespace
    cleaned = " ".join(str(description).split())
    
    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()
    
    return cleaned


def cleanse_transaction_data(file_path: str, output_path: Optional[str] = None) -> Dict:
    """Cleanse transaction data from file.
    
    Normalizes:
    - Date formats
    - Amount formats
    - Description text
    
    Args:
        file_path: Path to source file
        output_path: Optional path to save cleansed file (default: archive/processed/)
        
    Returns:
        Dictionary with:
        - cleansed_file_path: Path to cleansed file
        - records_processed: Number of records processed
        - records_valid: Number of valid records
        - records_invalid: Number of invalid records
        - errors: List of errors encountered
    """
    errors = []
    records_processed = 0
    records_valid = 0
    records_invalid = 0
    
    delimiter = detect_delimiter(file_path)
    
    # Read source file
    try:
        df = pd.read_csv(file_path, delimiter=delimiter, dtype=str, keep_default_na=False)
    except Exception as e:
        errors.append(f"Error reading file: {e}")
        return {
            "cleansed_file_path": None,
            "records_processed": 0,
            "records_valid": 0,
            "records_invalid": 0,
            "errors": errors
        }
    
    records_processed = len(df)
    
    # Normalize date column (try to find date column)
    date_columns = [col for col in df.columns if 'date' in col.lower()]
    if date_columns:
        date_col = date_columns[0]
        df['_parsed_date'] = df[date_col].apply(parse_date)
        invalid_dates = df['_parsed_date'].isna().sum()
        if invalid_dates > 0:
            errors.append(f"Warning: {invalid_dates} records have invalid dates")
    else:
        errors.append("Warning: No date column found")
        df['_parsed_date'] = None
    
    # Normalize amount column
    amount_columns = [col for col in df.columns if 'amount' in col.lower()]
    if amount_columns:
        amount_col = amount_columns[0]
        df['_parsed_amount'] = df[amount_col].apply(clean_amount)
        invalid_amounts = df['_parsed_amount'].isna().sum()
        if invalid_amounts > 0:
            errors.append(f"Warning: {invalid_amounts} records have invalid amounts")
    else:
        errors.append("Warning: No amount column found")
        df['_parsed_amount'] = None
    
    # Normalize description columns
    desc_columns = [col for col in df.columns if any(word in col.lower() for word in ['description', 'memo', 'detail'])]
    for desc_col in desc_columns:
        df[desc_col] = df[desc_col].apply(normalize_description)
    
    # Identify valid records (have both date and amount)
    valid_mask = df['_parsed_date'].notna() & df['_parsed_amount'].notna()
    records_valid = valid_mask.sum()
    records_invalid = (~valid_mask).sum()
    
    # Determine output path
    if output_path is None:
        # Create output path maintaining structure in 01_processed/
        source_path = Path(file_path)
        archive_root = get_default_archive_root()
        
        # Check if file is in new structure (00_raw/)
        parts = source_path.parts
        try:
            if '00_raw' in parts or ('raw' in parts and '00_raw' not in parts):
                # Maintain structure: 00_raw/... or raw/... -> 01_processed/...
                archive_key = '00_raw' if '00_raw' in parts else 'raw'
                archive_idx = parts.index(archive_key)
                relative_parts = parts[archive_idx + 1:]  # Get path after archive directory
                output_dir = Path(archive_root) / "01_processed" / Path(*relative_parts[:-1])  # All but filename
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / f"cleansed_{source_path.name}"
            else:
                # Fallback: use default structure
                output_dir = Path(archive_root) / "01_processed"
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / f"cleansed_{source_path.name}"
        except:
            # Fallback: use default structure
            output_dir = Path(archive_root) / "01_processed"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"cleansed_{source_path.name}"
    
    # Save cleansed file (keep original columns, add parsed columns)
    df.to_csv(output_path, index=False, sep=delimiter)
    
    return {
        "cleansed_file_path": str(output_path),
        "records_processed": records_processed,
        "records_valid": records_valid,
        "records_invalid": records_invalid,
        "errors": errors
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m finance_app.agents.data_curation.cleansing <file_path> [output_path]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        result = cleanse_transaction_data(file_path, output_path)
        print(f"✓ Data cleansed successfully")
        print(f"  Cleansed file: {result['cleansed_file_path']}")
        print(f"  Records processed: {result['records_processed']}")
        print(f"  Records valid: {result['records_valid']}")
        print(f"  Records invalid: {result['records_invalid']}")
        if result['errors']:
            print(f"  Errors/Warnings: {', '.join(result['errors'])}")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

