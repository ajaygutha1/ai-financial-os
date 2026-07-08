import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRun(UUIDPKMixin, TimestampMixin, Base):
    """One invocation of an agent, start to finish -- may span several
    underlying Claude API calls (see AIAuditLog, one row per call) if the
    agent goes through a tool-calling loop before producing a final answer."""

    __tablename__ = "agent_run"
    __table_args__ = (
        Index("ix_agent_run_user_created_at", "user_id", "created_at"),
        Index("ix_agent_run_agent_name", "agent_name"),
    )

    # Nullable + SET NULL (not CASCADE): the run record is part of the AI
    # decision trail and should survive account deletion, same reasoning as
    # audit_log's user_id.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=AgentRunStatus.RUNNING)
    user_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
