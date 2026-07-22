import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class RefreshToken(UUIDPKMixin, TimestampMixin, Base):
    """Tracks every refresh token ever issued, keyed by its JWT `jti` claim,
    to make rotation-with-reuse-detection possible: the JWT alone can't
    express "has this already been used" since it's stateless by design.

    `family_id` groups one continuous rotation chain starting at a single
    login -- each successful /refresh revokes the presented row and inserts
    a new one in the *same* family. If an already-revoked token is ever
    presented again, that's a strong signal the token was copied (stolen):
    the legitimate client already rotated past it, so whoever just
    presented it isn't the legitimate client. The whole family gets revoked
    in that case, forcing a fresh login rather than trusting the chain
    further.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_family_id", "family_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jti: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
