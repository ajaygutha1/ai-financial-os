import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import UUIDPKMixin


class SyncJobStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReconciliationStatus(StrEnum):
    MATCHED = "matched"
    DISCREPANCY = "discrepancy"
    SKIPPED = "skipped"


class SyncJob(UUIDPKMixin, Base):
    __tablename__ = "sync_job"
    __table_args__ = (
        Index("ix_sync_job_account_id", "account_id"),
        Index("ix_sync_job_status", "status"),
        Index(
            "ux_sync_job_idempotency_key_active",
            "idempotency_key",
            unique=True,
            postgresql_where=text("status != 'failed'"),
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SyncJobStatus.RUNNING.value
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cursor_before: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cursor_after: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    reconciliation_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    discrepancy_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
