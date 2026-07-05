import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import UUIDPKMixin


class TransactionProvenance(UUIDPKMixin, Base):
    __tablename__ = "transaction_provenance"
    __table_args__ = (
        Index("ix_transaction_provenance_transaction_id", "transaction_id"),
        Index("ix_transaction_provenance_sync_job_id", "sync_job_id"),
    )

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    # Nullable: CSV-imported transactions get provenance too but have no sync_job.
    sync_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sync_job.id", ondelete="SET NULL"), nullable=True
    )
    step: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
