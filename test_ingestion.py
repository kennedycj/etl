"""Test file ingestion tool."""

import sys
from finance_app.agents.data_curation.ingestion import ingest_file, load_metadata

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_ingestion.py <file_path> [institution]")
        print("\nExample:")
        print("  python test_ingestion.py checking_statement_example.tsv")
        print("  python test_ingestion.py checking_statement_example.tsv boa")
        sys.exit(1)
    
    file_path = sys.argv[1]
    institution = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        print(f"Ingesting file: {file_path}")
        result = ingest_file(file_path, institution)
        
        print("\n[OK] File ingested successfully!")
        print(f"\nArchive Path: {result['archive_path']}")
        print(f"File Hash: {result['file_hash']}")
        print(f"Metadata: {result['metadata_path']}")
        print(f"\nMetadata Contents:")
        import json
        print(json.dumps(result['metadata'], indent=2))
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

