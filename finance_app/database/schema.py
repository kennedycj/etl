"""Database schema creation and management."""

from finance_app.database.connection import Base, create_database_engine
from finance_app.database.models import AccountModel, TransactionModel, BlockModel


def create_tables(engine, drop_existing=False):
    """Create all database tables.
    
    Args:
        engine: SQLAlchemy engine
        drop_existing: If True, drop existing tables before creating (destructive!)
    """
    if drop_existing:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m finance_app.database.schema <database_url> [--drop]")
        print("Example: python -m finance_app.database.schema postgresql://user:pass@localhost/finance")
        sys.exit(1)
    
    database_url = sys.argv[1]
    drop_existing = "--drop" in sys.argv
    
    engine = create_database_engine(database_url)
    create_tables(engine, drop_existing=drop_existing)
    print("Database tables created successfully!")

