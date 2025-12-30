"""Common types and enums for finance models."""

from enum import Enum


class TransactionStatus(str, Enum):
    """Transaction reconciliation status."""
    PENDING = "pending"
    POSTED = "posted"
    CLEARED = "cleared"
    RECONCILED = "reconciled"


class TransactionType(str, Enum):
    """Type of transaction."""
    PURCHASE = "purchase"
    PAYMENT = "payment"
    TRANSFER = "transfer"
    INTEREST = "interest"
    DIVIDEND = "dividend"
    FEE = "fee"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    ADJUSTMENT = "adjustment"


class ReconcileStatus(str, Enum):
    """Reconciliation status."""
    UNRECONCILED = "unreconciled"
    CLEARED = "cleared"
    RECONCILED = "reconciled"

