import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import UUIDPKMixin

# Named DomainEventLog (not DomainEvent) to avoid colliding with the Pydantic
# DomainEvent base class in app/events/domain_event.py.


class DomainEventLog(UUIDPKMixin, Base):
    __tablename__ = "domain_events"
    __table_args__ = (
        Index("ix_domain_events_aggregate", "aggregate_type", "aggregate_id"),
        Index("ix_domain_events_event_type", "event_type"),
        Index("ix_domain_events_occurred_at", "occurred_at"),
    )

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # No FK on aggregate_id -- deliberately polymorphic (transaction/account/sync_job).
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
