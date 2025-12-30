"""Pipeline orchestrator - run full data curation pipeline on files."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from finance_app.agents.data_curation.archive_scanner import (
    get_raw_archive_path, get_processed_archive_path, get_processing_state_path,
    load_processing_state, mark_file_processed, infer_file_metadata_from_path,
    create_processed_file_path, ensure_directory_structure_exists, save_processing_state
)
from finance_app.agents.data_curation.ingestion import calculate_file_hash, detect_file_format
from finance_app.agents.data_curation.validation import validate_file
from finance_app.agents.data_curation.cleansing import cleanse_transaction_data


def create_file_metadata_for_existing_file(file_path: Path, raw_root: Path) -> Dict:
    """Create metadata for a file that's already in the archive structure.
    
    Since files are manually placed in 00_raw/, we just create metadata without moving them.
    """
    from uuid import uuid4
    
    file_hash = calculate_file_hash(str(file_path))
    file_stats = file_path.stat()
    path_metadata = infer_file_metadata_from_path(file_path, raw_root)
    
    metadata = {
        "ingestion_id": str(uuid4()),
        "original_filename": file_path.name,
        "original_path": str(file_path.absolute()),
        "archive_path": str(file_path.absolute()),  # File stays where it is
        "archive_filename": file_path.name,
        "file_format": detect_file_format(str(file_path)),
        "file_hash": file_hash,
        "file_size_bytes": file_stats.st_size,
        "ingestion_timestamp": datetime.utcnow().isoformat(),
        **path_metadata  # Include inferred metadata (category, institution, account_type, dates)
    }
    
    # Save metadata file next to the source file
    metadata_path = file_path.parent / f"{file_path.name}.metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return metadata


def process_file_through_pipeline(file_path: Path, database_url: Optional[str] = None,
                                  dry_run: bool = False) -> Dict:
    """Process a single file through the full pipeline.
    
    Pipeline stages:
    1. Create metadata (file already in place)
    2. Validate file structure
    3. Cleanse data
    4. Deduplicate (requires database)
    5. Load to database (requires database - not yet implemented)
    
    Args:
        file_path: Path to file in 00_raw/
        database_url: Database connection string (required for deduplication)
        dry_run: If True, don't mark file as processed
        
    Returns:
        Dictionary with processing results
    """
    from uuid import uuid4
    
    raw_root = get_raw_archive_path()
    processed_root = get_processed_archive_path()
    
    results = {
        "file_path": str(file_path),
        "stages": {},
        "success": False,
        "errors": []
    }
    
    try:
        # Stage 1: Create metadata (file already in archive structure)
        print(f"\n[Stage 1] Creating metadata for: {file_path.name}")
        try:
            metadata = create_file_metadata_for_existing_file(file_path, raw_root)
            results["stages"]["metadata"] = {"success": True, "metadata": metadata}
        except Exception as e:
            results["stages"]["metadata"] = {"success": False, "error": str(e)}
            results["errors"].append(f"Metadata creation failed: {e}")
            return results
        
        # Stage 2: Validate file structure
        print(f"[Stage 2] Validating file structure...")
        try:
            validation_result = validate_file(str(file_path))
            results["stages"]["validation"] = validation_result
            if not validation_result.get("is_valid"):
                results["errors"].append("Validation failed - check structure")
        except Exception as e:
            results["stages"]["validation"] = {"success": False, "error": str(e)}
            results["errors"].append(f"Validation failed: {e}")
        
        # Stage 3: Cleanse data
        processed_file_path = None
        print(f"[Stage 3] Cleansing data...")
        try:
            # Create output path maintaining structure in 01_processed/
            processed_file_path = create_processed_file_path(file_path, raw_root, processed_root)
            processed_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Store for later stages
            results["processed_file_path"] = str(processed_file_path)
            
            cleansing_result = cleanse_transaction_data(str(file_path), str(processed_file_path))
            results["stages"]["cleansing"] = cleansing_result
            if cleansing_result.get("records_valid", 0) == 0:
                results["errors"].append("No valid records after cleansing")
        except Exception as e:
            results["stages"]["cleansing"] = {"success": False, "error": str(e)}
            results["errors"].append(f"Cleansing failed: {e}")
        
        # Stage 4: Deduplication (requires database)
        if database_url and processed_file_path and processed_file_path.exists():
            print(f"[Stage 4] Deduplicating against database...")
            try:
                from finance_app.database.connection import create_database_engine, get_session
                from finance_app.agents.data_curation.deduplication import deduplicate_transactions
                from finance_app.agents.data_curation.archive_scanner import parse_cleansed_csv_to_transactions
                
                # Note: parse_cleansed_csv_to_transactions needs to be moved to a shared location
                # For now, we'll skip deduplication in orchestrator and handle separately
                results["stages"]["deduplication"] = {"skipped": True, "note": "Deduplication to be handled separately"}
            except Exception as e:
                results["stages"]["deduplication"] = {"success": False, "error": str(e)}
                results["errors"].append(f"Deduplication failed: {e}")
        else:
            results["stages"]["deduplication"] = {"skipped": True, "note": "Database URL not provided"}
        
        # Stage 5: Load to database (not yet implemented)
        results["stages"]["loading"] = {"skipped": True, "note": "Loading to database not yet implemented"}
        
        # Mark as processed if successful
        if not dry_run and len(results["errors"]) == 0:
            state = load_processing_state()
            mark_file_processed(file_path, state, metadata)
            save_processing_state(state)
        
        results["success"] = len(results["errors"]) == 0
        
    except Exception as e:
        results["errors"].append(f"Pipeline error: {e}")
        import traceback
        results["traceback"] = traceback.format_exc()
    
    return results


def process_all_files(database_url: Optional[str] = None, dry_run: bool = False) -> Dict:
    """Process all unprocessed files in 00_raw/ through the pipeline.
    
    Args:
        database_url: Database connection string
        dry_run: If True, don't mark files as processed
        
    Returns:
        Dictionary with processing summary
    """
    from finance_app.agents.data_curation.archive_scanner import get_files_to_process
    
    ensure_directory_structure_exists(get_raw_archive_path().parent)
    
    files_to_process = get_files_to_process(force_reprocess=False)
    
    summary = {
        "total_files": len(files_to_process),
        "processed": 0,
        "failed": 0,
        "results": []
    }
    
    print(f"\n{'='*70}")
    print(f"PROCESSING {len(files_to_process)} FILE(S)")
    print(f"{'='*70}")
    
    for file_path, file_info in files_to_process:
        print(f"\nProcessing: {file_info['relative_path']}")
        result = process_file_through_pipeline(file_path, database_url, dry_run)
        summary["results"].append(result)
        
        if result["success"]:
            summary["processed"] += 1
            print(f"✓ Successfully processed: {file_path.name}")
        else:
            summary["failed"] += 1
            print(f"✗ Failed to process: {file_path.name}")
            for error in result.get("errors", []):
                print(f"  Error: {error}")
    
    print(f"\n{'='*70}")
    print(f"SUMMARY: {summary['processed']} processed, {summary['failed']} failed")
    print(f"{'='*70}")
    
    return summary


if __name__ == "__main__":
    import sys
    import os
    
    database_url = os.getenv("DATABASE_URL")
    dry_run = "--dry-run" in sys.argv
    
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: python -m finance_app.agents.data_curation.pipeline_orchestrator [--dry-run]")
        print("\nEnvironment variables:")
        print("  DATABASE_URL: Database connection string (optional, for deduplication)")
        print("  FINANCE_ARCHIVE_ROOT: Archive root directory (default: ~/Documents/finance_archive)")
        print("\nOptions:")
        print("  --dry-run: Process files but don't mark as processed")
        sys.exit(0)
    
    if not database_url:
        print("Warning: DATABASE_URL not set - deduplication will be skipped")
    
    summary = process_all_files(database_url, dry_run)
    
    if summary["failed"] > 0:
        sys.exit(1)

