import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.category import Category


class Merchant(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "merchant"
    __table_args__ = (
        Index(
            "ux_merchant_canonical_name_lower",
            text("lower(canonical_name)"),
            unique=True,
        ),
    )

    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("category.id", ondelete="SET NULL"), nullable=True
    )

    category: Mapped["Category | None"] = relationship(back_populates="merchants")
