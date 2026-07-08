import uuid
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class RecommendationStatus(StrEnum):
    ACTIVE = "active"
    DISMISSED = "dismissed"
    COMPLETED = "completed"


class AIRecommendation(UUIDPKMixin, TimestampMixin, Base):
    """A user-facing recommendation produced by an agent -- the structured,
    explainable deliverable. Distinct from AIAuditLog (the raw call-by-call
    trail): this is what the dashboard queries to show "your AI insights,"
    while AIAuditLog is the compliance/debugging record of how it was
    produced."""

    __tablename__ = "ai_recommendation"
    __table_args__ = (
        Index("ix_ai_recommendation_user_status", "user_id", "status"),
        Index("ix_ai_recommendation_agent_run_id", "agent_run_id"),
    )

    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_run.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    # Structured citations: which metrics/tool calls backed this
    # recommendation -- e.g. {"metrics_used": ["emergency_fund", "cash_flow"]}.
    citations: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RecommendationStatus.ACTIVE
    )
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
