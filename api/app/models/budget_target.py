import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.category import Category


class BudgetTarget(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "budget_targets"
    __table_args__ = (
        UniqueConstraint("user_id", "category_id", name="ux_budget_targets_user_category"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("category.id", ondelete="CASCADE"), nullable=False
    )
    monthly_target_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    category: Mapped["Category"] = relationship()
