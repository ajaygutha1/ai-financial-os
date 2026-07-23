import logging
import uuid
from collections.abc import Callable

from celery import Task
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.ingestion.connectors.base import Connector
from app.ingestion.connectors.coinbase_stub import CoinbaseStubConnector
from app.ingestion.connectors.plaid.dependency import get_plaid_client
from app.ingestion.connectors.plaid_connector import PlaidConnector
from app.ingestion.connectors.plaid_stub import PlaidStubConnector
from app.ingestion.connectors.robinhood_stub import RobinhoodStubConnector
from app.jobs.celery_app import celery_app
from app.models.account import Account, AccountSource
from app.repositories.connector_credential_repository import ConnectorCredentialRepository
from app.services.sync_service import SyncService

logger = logging.getLogger(__name__)

# Stub connectors, used whenever an account has no real linked credential --
# still the only path for Coinbase/Robinhood (Milestone 9 only builds a real
# connector for Plaid) and for any legacy/demo Plaid-sourced account created
# before real linking existed. Typed as Callable (not type[Connector]) since
# Connector is a Protocol -- a static type checker won't let you
# "instantiate a Protocol," even though these are all concrete, perfectly
# instantiable classes at runtime.
_CONNECTOR_FACTORIES: dict[str, Callable[[str], Connector]] = {
    AccountSource.PLAID.value: PlaidStubConnector,
    AccountSource.COINBASE.value: CoinbaseStubConnector,
    AccountSource.ROBINHOOD.value: RobinhoodStubConnector,
}


def build_connector_for_account(account: Account, db: Session) -> Connector:
    if not account.external_account_id:
        raise ValueError("Account has no external_account_id to sync against.")

    if account.source == AccountSource.PLAID.value and account.connector_credential_id is not None:
        credential = ConnectorCredentialRepository(db).get_by_id(account.connector_credential_id)
        if credential is None or credential.access_token_enc is None:
            raise ValueError(
                f"Account {account.id} has no usable Plaid credential to sync against."
            )
        return PlaidConnector(
            get_plaid_client(),
            access_token=credential.access_token_enc,
            external_account_id=account.external_account_id,
        )

    factory = _CONNECTOR_FACTORIES.get(account.source)
    if factory is None:
        raise ValueError(f"No connector available for account source '{account.source}'")
    return factory(account.external_account_id)


# Celery's `@task` decorator isn't fully typed, so mypy can't infer this
# function's signature through it; scoped ignores rather than a blanket
# per-module exclusion, since the function bodies themselves are still
# checked normally.
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[untyped-decorator]
def sync_account(self: Task, account_id: str) -> None:
    db = SessionLocal()
    try:
        account = db.get(Account, uuid.UUID(account_id))
        if account is None:
            logger.warning("sync_account: account %s not found, skipping", account_id)
            return

        connector = build_connector_for_account(account, db)
        # SyncService.run_sync's own idempotency guard keys off this exact
        # (account, cursor) pairing -- a retried attempt with an unchanged
        # cursor maps to the same key and short-circuits safely.
        idempotency_key = f"{account_id}:{account.last_sync_cursor or 'initial'}"
        SyncService(db).run_sync(
            account_id=account.id, connector=connector, idempotency_key=idempotency_key
        )
    except Exception as exc:
        # SyncService already marked the sync_job failed; this is what
        # applies Celery's retry/backoff on top of that.
        raise self.retry(exc=exc) from exc
    finally:
        db.close()


@celery_app.task  # type: ignore[untyped-decorator]
def sync_all_active_accounts() -> None:
    """Beat-scheduled fan-out over active, connector-sourced accounts."""
    db = SessionLocal()
    try:
        stmt = select(Account).where(
            Account.is_active.is_(True),
            Account.source.in_(list(_CONNECTOR_FACTORIES.keys())),
        )
        for account in db.scalars(stmt):
            sync_account.delay(str(account.id))
    finally:
        db.close()
