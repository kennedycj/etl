"""Data validation tools - validate file structure and content."""

import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd


class ValidationError(Exception):
    """Validation error."""
    pass


def detect_delimiter(file_path: str) -> str:
    """Detect delimiter (comma or tab) from file extension and content."""
    if file_path.lower().endswith('.csv'):
        return ','
    elif file_path.lower().endswith('.tsv'):
        return '\t'
    
    # Auto-detect by reading first line
    with open(file_path, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        comma_count = first_line.count(',')
        tab_count = first_line.count('\t')
        return ',' if comma_count > tab_count else '\t'


def validate_file_structure(file_path: str, expected_columns: Optional[List[str]] = None) -> Dict:
    """Validate file structure (format, columns, basic data types).
    
    Args:
        file_path: Path to file to validate
        expected_columns: Optional list of expected column names
        
    Returns:
        Dictionary with:
        - is_valid: Boolean
        - validation_errors: List of error messages
        - record_count: Number of records
        - columns: List of column names found
        - file_format: Detected format
    """
    errors = []
    columns = []
    record_count = 0
    file_format = "unknown"
    
    try:
        # Detect format
        if file_path.lower().endswith('.csv'):
            file_format = 'csv'
            delimiter = ','
        elif file_path.lower().endswith('.tsv'):
            file_format = 'tsv'
            delimiter = '\t'
        else:
            delimiter = detect_delimiter(file_path)
            file_format = 'csv' if delimiter == ',' else 'tsv'
        
        # Read first few rows to validate structure
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            columns = reader.fieldnames or []
            
            if not columns:
                errors.append("File has no header row or cannot be parsed")
                return {
                    "is_valid": False,
                    "validation_errors": errors,
                    "record_count": 0,
                    "columns": [],
                    "file_format": file_format
                }
            
            # Count records and check for empty file
            row_count = 0
            for row in reader:
                row_count += 1
                if row_count > 1000:  # Sample first 1000 rows for validation
                    break
            
            record_count = row_count
            
            # Check for expected columns if provided
            if expected_columns:
                missing = set(expected_columns) - set(columns)
                if missing:
                    errors.append(f"Missing expected columns: {', '.join(missing)}")
            
            # Check for empty file
            if record_count == 0:
                errors.append("File contains no data rows")
        
    except UnicodeDecodeError as e:
        errors.append(f"File encoding error: {e}")
    except Exception as e:
        errors.append(f"Error reading file: {e}")
    
    return {
        "is_valid": len(errors) == 0,
        "validation_errors": errors,
        "record_count": record_count,
        "columns": columns,
        "file_format": file_format
    }


def validate_data_types(file_path: str, sample_size: int = 100) -> Dict:
    """Validate data types in file (dates, amounts, etc.).
    
    Args:
        file_path: Path to file
        sample_size: Number of rows to sample for validation
        
    Returns:
        Dictionary with validation results
    """
    errors = []
    warnings = []
    
    try:
        delimiter = detect_delimiter(file_path)
        df = pd.read_csv(file_path, delimiter=delimiter, nrows=sample_size)
        
        # Check for Date column
        date_columns = [col for col in df.columns if 'date' in col.lower() or 'date' in col.lower()]
        if date_columns:
            for col in date_columns:
                # Try to parse dates
                try:
                    pd.to_datetime(df[col].dropna().head(10), errors='raise')
                except:
                    warnings.append(f"Column '{col}' may not contain valid dates")
        
        # Check for Amount column
        amount_columns = [col for col in df.columns if 'amount' in col.lower()]
        if amount_columns:
            for col in amount_columns:
                # Try to convert to numeric
                try:
                    pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='raise')
                except:
                    warnings.append(f"Column '{col}' may not contain valid numeric amounts")
        
    except Exception as e:
        errors.append(f"Error validating data types: {e}")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def validate_file(file_path: str, expected_columns: Optional[List[str]] = None) -> Dict:
    """Comprehensive file validation.
    
    Args:
        file_path: Path to file
        expected_columns: Optional expected column names
        
    Returns:
        Combined validation results
    """
    structure_result = validate_file_structure(file_path, expected_columns)
    type_result = validate_data_types(file_path)
    
    all_errors = structure_result["validation_errors"] + type_result["errors"]
    
    return {
        "is_valid": structure_result["is_valid"] and type_result["is_valid"],
        "validation_errors": all_errors,
        "warnings": type_result["warnings"],
        "record_count": structure_result["record_count"],
        "columns": structure_result["columns"],
        "file_format": structure_result["file_format"]
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m finance_app.agents.data_curation.validation <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    try:
        result = validate_file(file_path)
        if result["is_valid"]:
            print(f"✓ File is valid")
            print(f"  Records: {result['record_count']}")
            print(f"  Columns: {', '.join(result['columns'])}")
            print(f"  Format: {result['file_format']}")
        else:
            print(f"✗ File validation failed:")
            for error in result["validation_errors"]:
                print(f"  - {error}")
            sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

