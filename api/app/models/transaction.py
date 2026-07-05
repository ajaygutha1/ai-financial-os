import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Date, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.category import Category
    from app.models.merchant import Merchant


class TransactionType(StrEnum):
    PURCHASE = "purchase"
    PAYMENT = "payment"
    TRANSFER = "transfer"
    FEE = "fee"
    INTEREST = "interest"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    DIVIDEND = "dividend"
    BUY = "buy"
    SELL = "sell"
    REFUND = "refund"
    OTHER = "other"


class ImportSource(StrEnum):
    CSV = "csv"
    MANUAL = "manual"
    PLAID = "plaid"
    OFX = "ofx"
    COINBASE = "coinbase"
    ROBINHOOD = "robinhood"


class Transaction(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_user_posted_at", "user_id", "posted_at"),
        Index(
            "ux_transactions_account_external_id",
            "account_id",
            "external_transaction_id",
            unique=True,
            postgresql_where=text("external_transaction_id IS NOT NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    posted_at: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    merchant_raw: Mapped[str | None] = mapped_column(String(500), nullable=True)
    merchant_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Plain strings, kept alongside the FK columns below through Milestone 2
    # (expand/contract migration pattern -- see migration 0002's docstring).
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("category.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchant.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transaction_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TransactionType.PURCHASE
    )
    is_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )
    import_source: Mapped[str] = mapped_column(String(32), nullable=False, default=ImportSource.CSV)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    external_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    account: Mapped["Account"] = relationship(back_populates="transactions")
    category_ref: Mapped["Category | None"] = relationship()
    merchant: Mapped["Merchant | None"] = relationship()
