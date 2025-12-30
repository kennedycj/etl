"""Account model - represents a financial account."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AccountType(str, Enum):
    """Account type enumeration."""
    
    # Banking
    CHECKING = "checking"
    SAVINGS = "savings"
    CD = "cd"
    
    # Credit/Debt
    CREDIT_CARD = "credit_card"
    HELOC = "heloc"
    MORTGAGE = "mortgage"
    
    # Investment
    BROKERAGE = "brokerage"
    IRA_TRADITIONAL = "ira_traditional"
    IRA_ROTH = "ira_roth"
    IRA_ROLLOVER = "ira_rollover"
    K401 = "401k"
    K529 = "529"
    ABLE = "able"


class AccountCategory(str, Enum):
    """Account category for accounting purposes."""
    ASSET = "asset"
    LIABILITY = "liability"
    INVESTMENT = "investment"
    DEBT = "debt"


class Account(BaseModel):
    """Account model for financial accounts."""
    
    id: UUID = Field(default_factory=uuid4, description="Unique account identifier")
    name: str = Field(..., description="Account name")
    account_type: AccountType = Field(..., description="Type of account")
    institution_name: str = Field(..., description="Financial institution name")
    account_number_masked: Optional[str] = Field(None, description="Last 4 digits or masked account number")
    currency: str = Field(default="USD", description="Currency code")
    open_date: datetime = Field(default_factory=datetime.utcnow, description="Account opening date")
    close_date: Optional[datetime] = Field(None, description="Account closing date (if closed)")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    class Config:
        """Pydantic config."""
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }
    
    @property
    def category(self) -> AccountCategory:
        """Determine account category based on type."""
        if self.account_type in [AccountType.CHECKING, AccountType.SAVINGS, AccountType.CD]:
            return AccountCategory.ASSET
        elif self.account_type in [AccountType.CREDIT_CARD, AccountType.HELOC, AccountType.MORTGAGE]:
            return AccountCategory.LIABILITY
        elif self.account_type in [
            AccountType.BROKERAGE, AccountType.IRA_TRADITIONAL, AccountType.IRA_ROTH,
            AccountType.IRA_ROLLOVER, AccountType.K401, AccountType.K529, AccountType.ABLE
        ]:
            return AccountCategory.INVESTMENT
        else:
            return AccountCategory.ASSET
    
    @property
    def is_closed(self) -> bool:
        """Check if account is closed."""
        return self.close_date is not None

