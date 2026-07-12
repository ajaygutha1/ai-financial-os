import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import UUIDPKMixin

# AI-specific audit trail -- kept separate from the generic system audit_log
# (Milestone 1/2) since the two have different volumes and query patterns.
# One row per underlying Claude API call (an agent_run's tool-calling loop
# produces several). Hash-chained and immutable, same tamper-evident pattern
# as audit_log (Milestone 2, Enhancement 2) -- see migration 0003.


class AIAuditLog(UUIDPKMixin, Base):
    __tablename__ = "ai_audit_log"
    __table_args__ = (Index("ix_ai_audit_log_agent_run_id", "agent_run_id"),)

    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_run.id", ondelete="CASCADE"), nullable=False
    )
    # Nullable + SET NULL: same reasoning as agent_run.user_id -- the audit
    # record should survive account deletion.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    stop_reason: Mapped[str] = mapped_column(String(32), nullable=False)
    tokens_input: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_output: Mapped[int] = mapped_column(Integer, nullable=False)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Hash chain -- computed by AIAuditLogRepository.record(), never a DB
    # default. Genesis row uses GENESIS_HASH as prev_hash.
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
