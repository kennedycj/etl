"""Test database models and schema creation."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from finance_app.database.connection import Base, create_database_engine, get_session
from finance_app.database.models import AccountModel, TransactionModel, BlockModel
from finance_app.models.account import AccountType


def test_model_creation():
    """Test creating model instances."""
    
    # Create an account
    account = AccountModel(
        id=uuid4(),
        name="Primary Checking",
        account_type=AccountType.CHECKING.value,
        institution_name="Bank of America",
        account_number_masked="1234",
        currency="USD",
        open_date=datetime.utcnow()
    )
    
    print(f"Created account: {account}")
    
    # Create a transaction
    transaction = TransactionModel(
        id=uuid4(),
        account_id=account.id,
        transaction_date=datetime(2025, 12, 12),
        amount=Decimal("-26.69"),
        currency="USD",
        description="LYFT *TEMP AUTH HOLD",
        simple_description="Lyft",
        category="Travel",
        status="pending",
        is_external=True
    )
    
    print(f"Created transaction: {transaction}")
    print(f"Transaction amount: {transaction.amount}")
    print(f"Transaction date: {transaction.transaction_date}")


def test_table_creation(database_url: str):
    """Test creating tables in database."""
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    print("✓ Tables created successfully!")
    
    # Test session
    session = get_session(engine)
    print(f"✓ Session created: {session}")
    session.close()


if __name__ == "__main__":
    import sys
    
    print("Testing model creation...")
    test_model_creation()
    
    if len(sys.argv) > 1:
        database_url = sys.argv[1]
        print(f"\nTesting table creation with database: {database_url}")
        test_table_creation(database_url)
    else:
        print("\nTo test table creation, provide database URL:")
        print("  python test_database_models.py postgresql://user:pass@localhost/dbname")

