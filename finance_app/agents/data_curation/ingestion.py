"""File ingestion tools - archive source files with metadata."""

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from uuid import uuid4


def get_default_archive_root() -> str:
    """Get default archive root directory.
    
    Uses FINANCE_ARCHIVE_ROOT environment variable if set,
    otherwise defaults to user's Documents/finance_archive directory.
    
    Returns:
        Archive root path as string
    """
    archive_root = os.getenv("FINANCE_ARCHIVE_ROOT")
    if archive_root:
        return archive_root
    
    # Default to user's Documents folder (outside repo)
    user_home = Path.home()
    if os.name == 'nt':  # Windows
        default_path = user_home / "Documents" / "finance_archive"
    else:  # Unix/Mac
        default_path = user_home / "finance_archive"
    
    return str(default_path)


class FileIngestionError(Exception):
    """Error during file ingestion."""
    pass


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of file.
    
    Args:
        file_path: Path to file
        
    Returns:
        SHA-256 hash as hex string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def detect_institution_from_filename(filename: str) -> str:
    """Detect institution name from filename.
    
    Args:
        filename: Original filename
        
    Returns:
        Institution name (lowercase, default: 'unknown')
    """
    filename_lower = filename.lower()
    
    # Common patterns
    if 'boa' in filename_lower or 'bank of america' in filename_lower:
        return 'boa'
    elif 'chase' in filename_lower:
        return 'chase'
    elif 'wells fargo' in filename_lower or 'wellsfargo' in filename_lower:
        return 'wells_fargo'
    elif 'citi' in filename_lower or 'citibank' in filename_lower:
        return 'citi'
    elif 'fidelity' in filename_lower:
        return 'fidelity'
    elif 'vanguard' in filename_lower:
        return 'vanguard'
    elif 'schwab' in filename_lower:
        return 'schwab'
    else:
        return 'unknown'


def detect_file_format(file_path: str) -> str:
    """Detect file format from extension and content.
    
    Args:
        file_path: Path to file
        
    Returns:
        File format: 'csv', 'tsv', 'ofx', 'qfx', or 'unknown'
    """
    ext = Path(file_path).suffix.lower()
    
    if ext == '.csv':
        return 'csv'
    elif ext == '.tsv':
        return 'tsv'
    elif ext in ['.ofx', '.OFX']:
        return 'ofx'
    elif ext in ['.qfx', '.QFX']:
        return 'qfx'
    else:
        return 'unknown'


def create_archive_path(institution: str, year: int, original_filename: str, 
                       archive_root: Optional[str] = None) -> Tuple[str, str]:
    """Create archive path for file.
    
    Args:
        institution: Institution name
        year: Year of data
        original_filename: Original filename
        archive_root: Root of archive directory (uses default if None)
        
    Returns:
        Tuple of (directory_path, filename)
    """
    if archive_root is None:
        archive_root = get_default_archive_root()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename_ext = Path(original_filename).suffix
    filename_stem = Path(original_filename).stem
    
    # Create safe filename: timestamp_originalname.ext
    safe_filename = f"{timestamp}_{filename_stem}{filename_ext}"
    
    # Directory structure: archive_root/raw/institution/year/
    archive_dir = Path(archive_root) / "raw" / institution / str(year)
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    return str(archive_dir), safe_filename


def ingest_file(source_file_path: str, institution: Optional[str] = None,
                archive_root: Optional[str] = None) -> Dict:
    """Ingest and archive a source file.
    
    This function:
    1. Validates file exists
    2. Calculates file hash
    3. Detects institution and format
    4. Archives to archive_root/raw/
    5. Creates metadata file
    
    Args:
        source_file_path: Path to source file to ingest
        institution: Institution name (auto-detected if None)
        archive_root: Root directory for archives (uses FINANCE_ARCHIVE_ROOT env var or default if None)
        
    Returns:
        Dictionary with:
        - archive_path: Path where file was archived
        - file_hash: SHA-256 hash
        - metadata_path: Path to metadata file
        - metadata: Metadata dictionary
    """
    source_path = Path(source_file_path)
    
    if not source_path.exists():
        raise FileIngestionError(f"Source file not found: {source_file_path}")
    
    if not source_path.is_file():
        raise FileIngestionError(f"Path is not a file: {source_file_path}")
    
    # Calculate file hash
    file_hash = calculate_file_hash(str(source_path))
    
    # Detect institution and format
    if institution is None:
        institution = detect_institution_from_filename(source_path.name)
    
    file_format = detect_file_format(str(source_path))
    
    # Determine year (default to current year, could parse from filename)
    year = datetime.now().year
    
    # Create archive path
    archive_dir, archive_filename = create_archive_path(
        institution, year, source_path.name, archive_root
    )
    archive_path = Path(archive_dir) / archive_filename
    
    # Copy file to archive (never modify original)
    shutil.copy2(source_path, archive_path)
    
    # Create metadata
    file_stats = source_path.stat()
    metadata = {
        "ingestion_id": str(uuid4()),
        "original_filename": source_path.name,
        "original_path": str(source_path.absolute()),
        "archive_path": str(archive_path.absolute()),
        "archive_filename": archive_filename,
        "institution": institution,
        "file_format": file_format,
        "file_hash": file_hash,
        "file_size_bytes": file_stats.st_size,
        "ingestion_timestamp": datetime.utcnow().isoformat()
    }
    
    # Save metadata to JSON file
    metadata_filename = archive_filename + ".metadata.json"
    metadata_path = Path(archive_dir) / metadata_filename
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return {
        "archive_path": str(archive_path),
        "file_hash": file_hash,
        "metadata_path": str(metadata_path),
        "metadata": metadata
    }


def load_metadata(metadata_path: str) -> Dict:
    """Load metadata from metadata file.
    
    Args:
        metadata_path: Path to metadata JSON file
        
    Returns:
        Metadata dictionary
    """
    with open(metadata_path, 'r') as f:
        return json.load(f)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m finance_app.agents.data_curation.ingestion <file_path> [institution]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    institution = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        result = ingest_file(file_path, institution)
        print(f"✓ File ingested successfully")
        print(f"  Archive path: {result['archive_path']}")
        print(f"  File hash: {result['file_hash']}")
        print(f"  Metadata: {result['metadata_path']}")
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

