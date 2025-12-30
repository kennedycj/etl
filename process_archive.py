"""Main script to process all files in 00_raw/ archive directory.

This is the main entry point for the curation agent's periodic scanning job.
Run this script (e.g., via cron) to process new files through the pipeline.
"""

import os
import sys
from finance_app.agents.data_curation.pipeline_orchestrator import process_all_files

if __name__ == "__main__":
    database_url = os.getenv("DATABASE_URL")
    dry_run = "--dry-run" in sys.argv or "--dryrun" in sys.argv
    force = "--force" in sys.argv
    
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Process all unprocessed files in 00_raw/ through the curation pipeline.")
        print("\nUsage:")
        print("  python process_archive.py [--dry-run] [--force]")
        print("\nOptions:")
        print("  --dry-run    Process files but don't mark as processed (for testing)")
        print("  --force      Reprocess all files (ignore processing state)")
        print("\nEnvironment variables:")
        print("  DATABASE_URL         Database connection string (for deduplication)")
        print("  FINANCE_ARCHIVE_ROOT Archive root directory")
        print("                       (default: ~/Documents/finance_archive)")
        print("\nExample:")
        print("  $env:DATABASE_URL='postgresql://user:pass@localhost/finance'")
        print("  python process_archive.py")
        sys.exit(0)
    
    if not database_url:
        print("Warning: DATABASE_URL not set - deduplication will be skipped")
        print("Set DATABASE_URL environment variable for full pipeline processing")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    summary = process_all_files(database_url, dry_run)
    
    if summary["failed"] > 0:
        print(f"\n⚠  {summary['failed']} file(s) failed processing")
        sys.exit(1)
    elif summary["processed"] == 0:
        print("\n✓ No files to process (all files are up to date)")
    else:
        print(f"\n✓ Successfully processed {summary['processed']} file(s)")

