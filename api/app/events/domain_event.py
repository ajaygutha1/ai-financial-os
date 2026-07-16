import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import BaseModel, Field

# Pydantic event models -- named DomainEvent to mirror the "domain event"
# pattern by name, but kept distinct from app.models.domain_event.DomainEventLog
# (the SQLAlchemy row) to avoid a naming collision between the two layers.


class DomainEvent(BaseModel):
    event_type: ClassVar[str]
    aggregate_type: ClassVar[str]

    aggregate_id: uuid.UUID
    # Added in Milestone 7 so the SSE stream can deliver only this user's own
    # events -- every event that exists today already happens inside a
    # user-scoped request, so this is always available at the call site.
    user_id: uuid.UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"aggregate_id", "user_id", "occurred_at"})


class TransactionsImported(DomainEvent):
    """Emitted once per ingestion run (CSV, OFX, or a connector sync), not
    once per transaction -- a large historical import shouldn't storm the
    event bus with thousands of individual events."""

    event_type: ClassVar[str] = "transactions.imported"
    aggregate_type: ClassVar[str] = "account"

    transaction_ids: list[uuid.UUID]
    imported_count: int
    duplicate_count: int
    import_source: str


class SyncCompleted(DomainEvent):
    event_type: ClassVar[str] = "sync.completed"
    aggregate_type: ClassVar[str] = "sync_job"

    account_id: uuid.UUID
    status: str
    reconciliation_status: str | None = None


class DuplicateDetected(DomainEvent):
    """Part of the domain event vocabulary for future consumers (e.g. an
    M6 fraud-detection signal); not currently emitted per-row from CSV/OFX
    ingestion -- duplicate_flagged provenance entries already cover that at
    the per-transaction level without event-storming the bus."""

    event_type: ClassVar[str] = "duplicate.detected"
    aggregate_type: ClassVar[str] = "transaction"

    is_duplicate_of: uuid.UUID


class TransferDetected(DomainEvent):
    """See DuplicateDetected's note -- defined for future targeted consumers,
    not emitted per-row from ingestion today."""

    event_type: ClassVar[str] = "transfer.detected"
    aggregate_type: ClassVar[str] = "transaction"

    matched_transaction_id: uuid.UUID
