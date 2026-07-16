import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.account import Account


class GoalStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Goal(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "goals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # A goal either tracks a real account's live balance (linked_account_id
    # set) or a manually-updated running total (manual_current_amount) --
    # never both, enforced at the schema/service layer rather than a DB
    # constraint since "exactly one of two nullable columns" isn't natural
    # to express declaratively here.
    linked_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    manual_current_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=GoalStatus.ACTIVE)

    linked_account: Mapped["Account | None"] = relationship()

    @property
    def current_amount(self) -> Decimal:
        """Live balance of the linked account if this goal tracks one,
        otherwise the manually-updated running total."""
        if self.linked_account is not None:
            return Decimal(self.linked_account.current_balance)
        return Decimal(self.manual_current_amount)

    @property
    def progress_pct(self) -> Decimal:
        # Quantized to match every other Numeric(18, 4) column's precision --
        # unlike those, this is pure Python Decimal arithmetic, which
        # otherwise returns a variable, input-dependent number of decimal
        # places rather than a fixed scale.
        _quantum = Decimal("0.0001")
        if self.target_amount <= 0:
            return Decimal("0").quantize(_quantum)
        pct = (self.current_amount / Decimal(self.target_amount)) * 100
        return min(pct, Decimal("100")).quantize(_quantum)
