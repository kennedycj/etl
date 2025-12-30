"""Archive scanner - scan 00_raw/ directory and process files through pipeline."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from finance_app.agents.data_curation.ingestion import calculate_file_hash, detect_file_format


def get_archive_root() -> Path:
    """Get the archive root directory (00_raw/ parent)."""
    archive_root = os.getenv("FINANCE_ARCHIVE_ROOT")
    if archive_root:
        return Path(archive_root)
    
    # Default to user's Documents folder
    user_home = Path.home()
    if os.name == 'nt':  # Windows
        default_path = user_home / "Documents" / "finance_archive"
    else:  # Unix/Mac
        default_path = user_home / "finance_archive"
    
    return default_path


def get_raw_archive_path() -> Path:
    """Get path to raw archive directory.
    
    Checks for raw/ first (existing structure), then 00_raw/ (new structure).
    """
    archive_root = get_archive_root()
    existing_path = archive_root / "raw"
    new_path = archive_root / "00_raw"
    
    # Prefer existing raw/ structure, fall back to new 00_raw/
    if existing_path.exists():
        return existing_path
    elif new_path.exists():
        return new_path
    else:
        # Return existing structure path (will be created if needed)
        return existing_path


def get_processed_archive_path() -> Path:
    """Get path to 01_processed/ directory."""
    return get_archive_root() / "01_processed"


def get_processing_state_path() -> Path:
    """Get path to processing state file (tracks processed files)."""
    return get_archive_root() / ".processing_state.json"


def load_processing_state() -> Dict[str, Dict]:
    """Load processing state (tracking which files have been processed)."""
    state_path = get_processing_state_path()
    if state_path.exists():
        with open(state_path, 'r') as f:
            return json.load(f)
    return {}


def save_processing_state(state: Dict[str, Dict]):
    """Save processing state."""
    state_path = get_processing_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)


def is_file_processed(file_path: Path, state: Dict[str, Dict]) -> bool:
    """Check if a file has already been processed."""
    file_str = str(file_path.resolve())
    if file_str not in state:
        return False
    
    file_state = state[file_str]
    file_hash = calculate_file_hash(str(file_path))
    
    # Check if file hash matches (file hasn't changed)
    return file_state.get('file_hash') == file_hash and file_state.get('processed', False)


def mark_file_processed(file_path: Path, state: Dict[str, Dict], metadata: Dict):
    """Mark a file as processed in the state."""
    file_str = str(file_path.resolve())
    file_hash = calculate_file_hash(str(file_path))
    
    state[file_str] = {
        'file_path': file_str,
        'file_hash': file_hash,
        'processed': True,
        'processed_at': datetime.utcnow().isoformat(),
        'metadata': metadata
    }


def scan_raw_archive() -> List[Tuple[Path, Dict]]:
    """Scan raw archive directory (00_raw/ or raw/) for files to process.
    
    Returns:
        List of tuples: (file_path, file_info_dict)
    """
    raw_path = get_raw_archive_path()
    
    if not raw_path.exists():
        return []
    
    # Find all CSV, TSV, OFX, QFX files
    file_extensions = ['.csv', '.tsv', '.ofx', '.qfx', '.CSV', '.TSV', '.OFX', '.QFX']
    files_to_process = []
    
    for ext in file_extensions:
        for file_path in raw_path.rglob(f'*{ext}'):
            if file_path.is_file():
                file_info = {
                    'path': file_path,
                    'relative_path': file_path.relative_to(raw_path),
                    'size': file_path.stat().st_size,
                    'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                    'format': detect_file_format(str(file_path))
                }
                files_to_process.append((file_path, file_info))
    
    return files_to_process


def get_files_to_process(force_reprocess: bool = False) -> List[Tuple[Path, Dict]]:
    """Get list of files that need processing.
    
    Args:
        force_reprocess: If True, include already-processed files
        
    Returns:
        List of tuples: (file_path, file_info_dict)
    """
    all_files = scan_raw_archive()
    
    if force_reprocess:
        return all_files
    
    state = load_processing_state()
    files_to_process = []
    
    for file_path, file_info in all_files:
        if not is_file_processed(file_path, state):
            files_to_process.append((file_path, file_info))
    
    return files_to_process


def infer_file_metadata_from_path(file_path: Path, raw_root: Path) -> Dict:
    """Infer metadata from file path structure.
    
    Expected structure: 00_raw/{category}/{institution}/{account_type}/{filename}
    Example: 00_raw/bank/chase/checking/2024-01-01_to_2024-01-31.csv
    """
    relative_path = file_path.relative_to(raw_root)
    parts = relative_path.parts
    
    metadata = {
        'relative_path': str(relative_path),
        'filename': file_path.name,
    }
    
    # Parse structure
    if len(parts) >= 1:
        metadata['category'] = parts[0]  # bank, brokerage, retirement, etc.
    
    if len(parts) >= 2:
        metadata['institution'] = parts[1]  # chase, fidelity, etc.
    
    if len(parts) >= 3:
        metadata['account_type'] = parts[2]  # checking, savings, taxable, etc.
    
    # Try to extract date range from filename
    # Support formats: 
    # - 2021_01_01_to_2021_12_31 (underscores)
    # - 2021-01-01_to_2021-12-31 (dashes)
    # - 2024-01-01_to_2024-01-31 (dashes, shorter format)
    filename = file_path.stem
    if '_to_' in filename:
        date_parts = filename.split('_to_')
        if len(date_parts) == 2:
            start_str = date_parts[0].replace('_', '-')  # Convert underscores to dashes
            end_str = date_parts[1].replace('_', '-')
            
            # Try parsing with different formats
            date_formats = ['%Y-%m-%d', '%Y_%m_%d']
            
            for fmt in date_formats:
                try:
                    start_date = datetime.strptime(start_str if fmt == '%Y-%m-%d' else date_parts[0], fmt)
                    end_date = datetime.strptime(end_str if fmt == '%Y-%m-%d' else date_parts[1], fmt)
                    metadata['start_date'] = start_date.isoformat()
                    metadata['end_date'] = end_date.isoformat()
                    break
                except ValueError:
                    continue
    
    return metadata


def create_processed_file_path(raw_file_path: Path, raw_root: Path, processed_root: Path) -> Path:
    """Create corresponding path in 01_processed/ maintaining structure."""
    relative_path = raw_file_path.relative_to(raw_root)
    return processed_root / relative_path


def ensure_directory_structure_exists(archive_root: Path):
    """Ensure the archive directory structure exists."""
    archive_root.mkdir(parents=True, exist_ok=True)
    (archive_root / "00_raw").mkdir(parents=True, exist_ok=True)
    (archive_root / "01_processed").mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    import sys
    
    force = '--force' in sys.argv
    
    print(f"Scanning archive: {get_raw_archive_path()}")
    files = get_files_to_process(force_reprocess=force)
    
    print(f"\nFound {len(files)} file(s) to process:")
    for file_path, file_info in files:
        print(f"  - {file_info['relative_path']}")
        print(f"    Format: {file_info['format']}, Size: {file_info['size']} bytes")
    
    if not files:
        print("\nNo files to process. All files are up to date.")
        print("Use --force to reprocess all files.")

