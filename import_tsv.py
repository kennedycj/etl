"""Simple script to import TSV file."""

import sys
from finance_app.database.connection import create_database_engine, get_session
from finance_app.importers.tsv_importer import import_tsv


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python import_tsv.py <database_url> <tsv_file>")
        print("\nExample:")
        print("  python import_tsv.py postgresql://user:pass@localhost/finance checking_statement_example.tsv")
        sys.exit(1)
    
    database_url = sys.argv[1]
    tsv_file = sys.argv[2]
    
    engine = create_database_engine(database_url)
    session = get_session(engine)
    
    try:
        print(f"Importing transactions from {tsv_file}...")
        accounts_created, transactions_imported = import_tsv(session, tsv_file)
        print(f"✓ Successfully imported {transactions_imported} transactions")
        if accounts_created > 0:
            print(f"✓ Created {accounts_created} new account(s)")
    except Exception as e:
        print(f"✗ Error: {e}")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()

