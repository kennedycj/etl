"""Quick test of the Account model."""

from finance_app.models.account import Account, AccountType


def test_account_creation():
    """Test creating a simple account."""
    account = Account(
        name="Primary Checking",
        account_type=AccountType.CHECKING,
        institution_name="Bank of America"
    )
    
    print(f"Created account: {account.name}")
    print(f"Type: {account.account_type}")
    print(f"Category: {account.category}")
    print(f"ID: {account.id}")
    print(f"Is Closed: {account.is_closed}")
    print(f"JSON: {account.model_dump_json(indent=2)}")


if __name__ == "__main__":
    test_account_creation()

