import uuid
from typing import ClassVar

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.ingestion.connectors.base import RawAccount, RawTransaction
from app.ingestion.connectors.plaid_stub import PlaidStubConnector
from app.ingestion.connectors.stub_base import PAGE_SIZE
from app.models.account import Account, AccountType
from app.models.domain_event import DomainEventLog
from app.models.sync_job import SyncJob, SyncJobStatus
from app.models.transaction import ImportSource, Transaction
from app.models.transaction_provenance import TransactionProvenance
from app.models.user import User
from app.services.sync_service import SyncService


class _FailingConnector:
    source: ClassVar[ImportSource] = ImportSource.PLAID

    def fetch_accounts(self) -> list[RawAccount]:
        return []

    def fetch_transactions(self, cursor: str | None) -> tuple[list[RawTransaction], str | None]:
        raise RuntimeError("simulated connector failure")


@pytest.fixture
def plaid_account(db_session: Session, test_user: User) -> Account:
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Plaid Linked Checking",
        account_type=AccountType.CHECKING.value,
        current_balance=0,
        source="plaid",
        external_account_id="plaid-ext-001",
    )
    db_session.add(account)
    db_session.commit()
    return account


def test_sync_creates_transactions_and_completes(
    db_session: Session, plaid_account: Account
) -> None:
    connector = PlaidStubConnector(plaid_account.external_account_id)
    job = SyncService(db_session).run_sync(
        account_id=plaid_account.id, connector=connector, idempotency_key="sync-key-1"
    )

    assert job.status == SyncJobStatus.COMPLETED.value
    assert job.cursor_after is not None
    assert job.reconciliation_status is not None
    # Self-consistency: a discrepancy always carries an amount, a match never does.
    if job.reconciliation_status == "discrepancy":
        assert job.discrepancy_amount is not None
    else:
        assert job.discrepancy_amount is None

    transactions = list(
        db_session.scalars(select(Transaction).where(Transaction.account_id == plaid_account.id))
    )
    assert len(transactions) == PAGE_SIZE

    provenance_row = db_session.scalar(
        select(TransactionProvenance).where(TransactionProvenance.sync_job_id == job.id)
    )
    assert provenance_row is not None

    imported_event = db_session.scalar(
        select(DomainEventLog).where(DomainEventLog.event_type == "transactions.imported")
    )
    completed_event = db_session.scalar(
        select(DomainEventLog).where(DomainEventLog.event_type == "sync.completed")
    )
    assert imported_event is not None
    assert completed_event is not None
    assert completed_event.aggregate_id == job.id


def test_sync_is_idempotent_for_same_key(db_session: Session, plaid_account: Account) -> None:
    connector = PlaidStubConnector(plaid_account.external_account_id)
    first_job = SyncService(db_session).run_sync(
        account_id=plaid_account.id, connector=connector, idempotency_key="sync-key-repeat"
    )

    second_job = SyncService(db_session).run_sync(
        account_id=plaid_account.id, connector=connector, idempotency_key="sync-key-repeat"
    )

    assert second_job.id == first_job.id

    transactions = list(
        db_session.scalars(select(Transaction).where(Transaction.account_id == plaid_account.id))
    )
    assert len(transactions) == PAGE_SIZE  # not duplicated


def test_failed_sync_is_marked_failed_and_retry_with_same_key_succeeds(
    db_session: Session, plaid_account: Account
) -> None:
    # run_sync deliberately re-raises after marking the job failed, so a
    # real Celery task can catch it and apply retry/backoff.
    with pytest.raises(RuntimeError, match="simulated connector failure"):
        SyncService(db_session).run_sync(
            account_id=plaid_account.id,
            connector=_FailingConnector(),
            idempotency_key="sync-key-retry",
        )

    failed_job = db_session.scalar(
        select(SyncJob).where(SyncJob.idempotency_key == "sync-key-retry")
    )
    assert failed_job is not None
    assert failed_job.status == SyncJobStatus.FAILED.value
    assert failed_job.error_message is not None

    retried_job = SyncService(db_session).run_sync(
        account_id=plaid_account.id,
        connector=PlaidStubConnector(plaid_account.external_account_id),
        idempotency_key="sync-key-retry",
    )
    assert retried_job.id != failed_job.id
    assert retried_job.status == SyncJobStatus.COMPLETED.value


def test_sync_requires_existing_account(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        SyncService(db_session).run_sync(
            account_id=uuid.uuid4(), connector=PlaidStubConnector("x"), idempotency_key="k"
        )


def test_sync_transaction_deduplicates_against_prior_csv_import(
    client, auth_headers: dict[str, str], db_session: Session, plaid_account: Account
) -> None:
    connector = PlaidStubConnector(plaid_account.external_account_id)
    SyncService(db_session).run_sync(
        account_id=plaid_account.id, connector=connector, idempotency_key="sync-key-2"
    )

    existing = db_session.scalars(
        select(Transaction).where(Transaction.account_id == plaid_account.id)
    ).first()
    assert existing is not None

    csv_row = (
        f"Date,Description,Amount\n{existing.posted_at.isoformat()},"
        f"{existing.merchant_raw},{existing.amount}\n"
    ).encode()

    response = client.post(
        "/api/v1/imports/csv",
        headers=auth_headers,
        data={"account_id": str(plaid_account.id), "debit_positive": "false"},
        files={"file": ("t.csv", csv_row, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["duplicate_count"] == 1
