"""SQLAlchemy database models."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Boolean, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship

from finance_app.database.connection import Base
from finance_app.models.common import ReconcileStatus, TransactionType


class AccountModel(Base):
    """SQLAlchemy model for accounts table."""
    
    __tablename__ = "accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    account_type = Column(String(50), nullable=False)  # Checking, Savings, Credit Card, etc.
    institution_name = Column(String(255), nullable=False)
    account_number_masked = Column(String(50), nullable=True)
    currency = Column(String(3), nullable=False, default="USD")
    open_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    close_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions = relationship("TransactionModel", back_populates="account", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Account(id={self.id}, name='{self.name}', type='{self.account_type}')>"


class TransactionModel(Base):
    """SQLAlchemy model for transactions table."""
    
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True)
    block_id = Column(UUID(as_uuid=True), ForeignKey("blocks.id"), nullable=True, index=True)
    
    # Date fields
    transaction_date = Column(DateTime, nullable=False, index=True)
    post_date = Column(DateTime, nullable=True)
    
    # Amount
    amount = Column(Numeric(19, 4), nullable=False)  # Supports large amounts with 4 decimal places
    currency = Column(String(3), nullable=False, default="USD")
    
    # Description fields
    description = Column(Text, nullable=False)
    simple_description = Column(Text, nullable=True)
    merchant_payee = Column(String(255), nullable=True)
    memo = Column(Text, nullable=True)
    user_description = Column(Text, nullable=True)
    
    # Classification
    category = Column(String(100), nullable=True, index=True)
    transaction_type = Column(SQLEnum(TransactionType), nullable=True)
    classification = Column(String(50), nullable=True)
    
    # Status
    status = Column(String(50), nullable=False, default="posted", index=True)
    reconcile_status = Column(SQLEnum(ReconcileStatus), nullable=False, default=ReconcileStatus.UNRECONCILED, index=True)
    reconcile_date = Column(DateTime, nullable=True)
    
    # Metadata
    reference_number = Column(String(100), nullable=True)
    tags = Column(JSON, nullable=True, default=list)  # Store as JSON array
    notes = Column(Text, nullable=True)
    is_external = Column(Boolean, nullable=False, default=True, index=True)
    
    # Audit fields
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    account = relationship("AccountModel", back_populates="transactions")
    block = relationship("BlockModel", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, account_id={self.account_id}, date={self.transaction_date}, amount={self.amount})>"


class BlockModel(Base):
    """SQLAlchemy model for double-entry transaction blocks."""
    
    __tablename__ = "blocks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    opened_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    closed_date = Column(DateTime, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions = relationship("TransactionModel", back_populates="block")
    
    def __repr__(self):
        return f"<Block(id={self.id}, name='{self.name}', closed={self.closed_date is not None})>"


class ImportLogModel(Base):
    """SQLAlchemy model for import logs - tracks all data imports."""
    
    __tablename__ = "import_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Source information
    source_file_path = Column(Text, nullable=False)
    archive_path = Column(Text, nullable=False)
    file_hash = Column(String(64), nullable=False)  # SHA-256 hash
    institution = Column(String(100), nullable=True)
    file_format = Column(String(20), nullable=False)  # csv, tsv, ofx, qfx
    
    # Import statistics
    records_processed = Column(Numeric(10, 0), nullable=False, default=0)
    records_inserted = Column(Numeric(10, 0), nullable=False, default=0)
    records_skipped = Column(Numeric(10, 0), nullable=False, default=0)  # Duplicates
    accounts_created = Column(Numeric(10, 0), nullable=False, default=0)
    
    # Status
    status = Column(String(50), nullable=False, default="pending")  # pending, success, failed
    error_message = Column(Text, nullable=True)
    
    # Quality metrics (stored as JSON)
    quality_metrics = Column(JSON, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Metadata
    import_metadata = Column(JSON, nullable=True)  # Additional metadata (renamed from 'metadata' to avoid SQLAlchemy conflict)
    
    def __repr__(self):
        return f"<ImportLog(id={self.id}, status='{self.status}', records={self.records_inserted})>"
