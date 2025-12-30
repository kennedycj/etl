"""Transaction model - represents a financial transaction."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from finance_app.models.common import ReconcileStatus, TransactionType


class Transaction(BaseModel):
    """Transaction model for financial transactions."""
    
    id: UUID = Field(default_factory=uuid4, description="Unique transaction identifier")
    account_id: UUID = Field(..., description="Account this transaction belongs to")
    block_id: Optional[UUID] = Field(None, description="Block ID if part of double-entry transaction")
    
    # Date fields
    transaction_date: datetime = Field(..., description="Transaction date")
    post_date: Optional[datetime] = Field(None, description="Post/settlement date")
    
    # Amount
    amount: Decimal = Field(..., description="Transaction amount (signed: positive=inflow, negative=outflow)")
    currency: str = Field(default="USD", description="Currency code")
    
    # Description fields
    description: str = Field(..., description="Original transaction description")
    simple_description: Optional[str] = Field(None, description="Simplified/cleaned description")
    merchant_payee: Optional[str] = Field(None, description="Merchant or payee name")
    memo: Optional[str] = Field(None, description="Additional memo/notes")
    user_description: Optional[str] = Field(None, description="User-added description")
    
    # Classification
    category: Optional[str] = Field(None, description="Transaction category")
    transaction_type: Optional[TransactionType] = Field(None, description="Type of transaction")
    classification: Optional[str] = Field(None, description="General classification (e.g., Personal, Business)")
    
    # Status
    status: str = Field(default="posted", description="Status: pending, posted, etc.")
    reconcile_status: ReconcileStatus = Field(default=ReconcileStatus.UNRECONCILED, description="Reconciliation status")
    reconcile_date: Optional[datetime] = Field(None, description="Date reconciled")
    
    # Metadata
    reference_number: Optional[str] = Field(None, description="Transaction reference number")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    notes: Optional[str] = Field(None, description="Additional notes")
    is_external: bool = Field(default=True, description="True for external transactions, false for internal transfers")
    
    # Audit fields
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Record update timestamp")
    
    class Config:
        """Pydantic config."""
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
            Decimal: str
        }

