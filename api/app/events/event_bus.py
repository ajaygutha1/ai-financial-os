import json
import logging

from sqlalchemy.orm import Session

from app.core.redis import get_redis_client
from app.events.domain_event import DomainEvent
from app.models.domain_event import DomainEventLog

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(self, event: DomainEvent) -> DomainEventLog:
        """Writes the event row in the *same* transaction as the write that
        triggered it -- call this before commit, not after. True outbox
        correctness (the event can only exist if the triggering write
        actually committed) falls out of the existing one-Session-per-request
        pattern for free, with no separate outbox-relay process needed.
        """
        log_row = DomainEventLog(
            event_type=event.event_type,
            payload=event.payload(),
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            occurred_at=event.occurred_at,
        )
        self.db.add(log_row)
        self.db.flush()
        return log_row

    def dispatch(self, event: DomainEvent) -> None:
        """Best-effort live fan-out via Redis pub/sub, called *after* commit
        succeeds. Never raises -- a Redis outage must not fail the request.
        The durable source of truth is the domain_events table itself; a
        consumer needing guaranteed delivery reads that table rather than
        relying on this push.
        """
        try:
            client = get_redis_client()
            channel = f"domain_events.{event.aggregate_type}"
            client.publish(
                channel,
                json.dumps(
                    {
                        "event_type": event.event_type,
                        "aggregate_type": event.aggregate_type,
                        "aggregate_id": str(event.aggregate_id),
                        "occurred_at": event.occurred_at.isoformat(),
                        "payload": event.payload(),
                    }
                ),
            )
        except Exception:
            logger.warning("Failed to dispatch domain event %s", event.event_type, exc_info=True)
