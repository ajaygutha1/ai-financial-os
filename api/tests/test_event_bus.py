import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events.domain_event import TransactionsImported
from app.events.event_bus import EventBus
from app.models.account import Account
from app.models.domain_event import DomainEventLog


def test_csv_import_emits_transactions_imported_event(
    client: TestClient, auth_headers: dict[str, str], db_session: Session, test_account: Account
) -> None:
    response = client.post(
        "/api/v1/imports/csv",
        headers=auth_headers,
        data={"account_id": str(test_account.id), "debit_positive": "false"},
        files={
            "file": (
                "t.csv",
                b"Date,Description,Amount\n2026-05-01,Coffee Shop,-5.00\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 200

    event_row = db_session.scalar(
        select(DomainEventLog).where(DomainEventLog.event_type == "transactions.imported")
    )
    assert event_row is not None
    assert event_row.aggregate_type == "account"
    assert event_row.aggregate_id == test_account.id
    assert event_row.payload["imported_count"] == 1
    assert event_row.payload["duplicate_count"] == 0
    assert event_row.payload["import_source"] == "csv"


def test_event_record_is_rolled_back_with_its_transaction(db_session: Session) -> None:
    event_bus = EventBus(db_session)
    event = TransactionsImported(
        aggregate_id=uuid.uuid4(),
        transaction_ids=[],
        imported_count=0,
        duplicate_count=0,
        import_source="csv",
    )
    event_bus.record(event)
    db_session.rollback()

    remaining = db_session.scalar(
        select(DomainEventLog).where(DomainEventLog.aggregate_id == event.aggregate_id)
    )
    assert remaining is None


def test_dispatch_swallows_redis_errors(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise() -> None:
        raise ConnectionError("redis is down")

    monkeypatch.setattr("app.events.event_bus.get_redis_client", _raise)

    event_bus = EventBus(db_session)
    event = TransactionsImported(
        aggregate_id=uuid.uuid4(),
        transaction_ids=[],
        imported_count=0,
        duplicate_count=0,
        import_source="csv",
    )

    # Must not raise even though the Redis client is unavailable.
    event_bus.dispatch(event)
