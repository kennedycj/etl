"""Script to create database tables."""

import sys
from finance_app.database.schema import create_tables
from finance_app.database.connection import create_database_engine


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python create_tables.py <database_url> [--drop]")
        print("Example: python create_tables.py postgresql://user:pass@localhost/finance")
        print("\nOptions:")
        print("  --drop    Drop existing tables before creating (WARNING: destructive!)")
        sys.exit(1)
    
    database_url = sys.argv[1]
    drop_existing = "--drop" in sys.argv
    
    if drop_existing:
        response = input("WARNING: This will delete all existing tables! Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            sys.exit(0)
    
    engine = create_database_engine(database_url)
    create_tables(engine, drop_existing=drop_existing)
    print("✓ Database tables created successfully!")

