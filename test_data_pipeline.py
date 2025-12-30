"""Test the data curation pipeline with a real file."""

import sys
from pathlib import Path
from finance_app.agents.data_curation.ingestion import ingest_file, load_metadata
from finance_app.agents.data_curation.validation import validate_file
from finance_app.agents.data_curation.cleansing import cleanse_transaction_data


def test_pipeline_stage_1(file_path: str, institution: str = "boa"):
    """Test Stage 1: Ingestion (Archive)"""
    print("\n" + "="*60)
    print("STAGE 1: INGESTION (Archive)")
    print("="*60)
    
    try:
        result = ingest_file(file_path, institution=institution)
        print(f"\n[OK] File ingested successfully!")
        print(f"  Archive Path: {result['archive_path']}")
        print(f"  File Hash: {result['file_hash']}")
        print(f"  Institution: {result['metadata']['institution']}")
        print(f"  Format: {result['metadata']['file_format']}")
        print(f"  Size: {result['metadata']['file_size_bytes']} bytes")
        return result
    except Exception as e:
        print(f"\n[ERROR] Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_pipeline_stage_2(archive_path: str):
    """Test Stage 2: Validation"""
    print("\n" + "="*60)
    print("STAGE 2: VALIDATION")
    print("="*60)
    
    try:
        result = validate_file(archive_path)
        if result["is_valid"]:
            print(f"\n[OK] File validation passed!")
            print(f"  Records: {result['record_count']}")
            print(f"  Columns: {len(result['columns'])} columns")
            print(f"  Format: {result['file_format']}")
            if result['columns']:
                print(f"  Column names: {', '.join(result['columns'][:10])}")
                if len(result['columns']) > 10:
                    print(f"    ... and {len(result['columns']) - 10} more")
        else:
            print(f"\n[WARNING] Validation issues found:")
            for error in result['validation_errors']:
                print(f"  - {error}")
        return result
    except Exception as e:
        print(f"\n[ERROR] Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_pipeline_stage_3(archive_path: str):
    """Test Stage 3: Cleansing"""
    print("\n" + "="*60)
    print("STAGE 3: CLEANSING")
    print("="*60)
    
    try:
        result = cleanse_transaction_data(archive_path)
        print(f"\n[OK] Data cleansing completed!")
        print(f"  Cleansed file: {result['cleansed_file_path']}")
        print(f"  Records processed: {result['records_processed']}")
        print(f"  Records valid: {result['records_valid']}")
        print(f"  Records invalid: {result['records_invalid']}")
        if result['errors']:
            print(f"  Warnings: {', '.join(result['errors'])}")
        return result
    except Exception as e:
        print(f"\n[ERROR] Cleansing failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_full_pipeline(file_path: str, institution: str = "boa"):
    """Test the full pipeline through cleansing stage."""
    print("\n" + "="*60)
    print("DATA CURATION PIPELINE TEST")
    print("="*60)
    print(f"\nFile: {file_path}")
    print(f"Institution: {institution}")
    
    # Stage 1: Ingestion
    ingest_result = test_pipeline_stage_1(file_path, institution)
    if not ingest_result:
        return
    
    archive_path = ingest_result['archive_path']
    
    # Stage 2: Validation
    validation_result = test_pipeline_stage_2(archive_path)
    if not validation_result or not validation_result['is_valid']:
        print("\n[WARNING] Validation issues - proceeding anyway for testing")
    
    # Stage 3: Cleansing
    cleansing_result = test_pipeline_stage_3(archive_path)
    
    print("\n" + "="*60)
    print("PIPELINE TEST SUMMARY")
    print("="*60)
    print(f"✓ Stage 1 (Ingestion): Complete")
    print(f"  File archived to: {archive_path}")
    if validation_result:
        print(f"✓ Stage 2 (Validation): {'Passed' if validation_result['is_valid'] else 'Issues Found'}")
    if cleansing_result:
        print(f"✓ Stage 3 (Cleansing): Complete")
        print(f"  Cleansed file: {cleansing_result['cleansed_file_path']}")
    print("\nNext stages:")
    if cleansing_result:
        print(f"  - Stage 4: Deduplication (use test_deduplication.py)")
        print(f"    Command: python test_deduplication.py \"{cleansing_result['cleansed_file_path']}\" <database_url>")
    print("  - Stage 5: Quality Validation (not yet implemented)")
    print("  - Stage 6: Load to Database (not yet implemented)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_data_pipeline.py <file_path> [institution]")
        print("\nExample:")
        print('  python test_data_pipeline.py "C:\\Users\\19527\\Documents\\finance\\accounts\\bo2025_boa_main.csv" boa')
        sys.exit(1)
    
    file_path = sys.argv[1]
    institution = sys.argv[2] if len(sys.argv) > 2 else "boa"
    
    # Check if file exists
    if not Path(file_path).exists():
        print(f"[ERROR] File not found: {file_path}")
        sys.exit(1)
    
    test_full_pipeline(file_path, institution)

