import uuid

from sqlalchemy.orm import Session

from app.analytics.reconciliation import reconcile_account_balance
from app.core.exceptions import NotFoundError
from app.events.domain_event import SyncCompleted, TransactionsImported
from app.events.event_bus import EventBus
from app.ingestion.connectors.base import Connector
from app.ingestion.normalization.pipeline import run_connector_sync_pipeline
from app.models.account import Account
from app.models.sync_job import SyncJob, SyncJobStatus
from app.repositories.account_repository import AccountRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.merchant_repository import MerchantRepository
from app.repositories.sync_job_repository import SyncJobRepository
from app.repositories.transaction_provenance_repository import TransactionProvenanceRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.ingestion_common import make_pipeline_dependencies


class SyncService:
    """Orchestrates a single connector-driven sync: idempotency guard, fetch,
    normalize, persist, reconcile, emit events, finalize. This is where
    Enhancements 3 (provenance), 4 (idempotent cursor sync), and 5
    (reconciliation) converge -- everything built in Milestones 2.1-2.7
    composes here.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounts = AccountRepository(db)
        self.transactions = TransactionRepository(db)
        self.provenance = TransactionProvenanceRepository(db)
        self.audit_log = AuditLogRepository(db)
        self.merchants = MerchantRepository(db)
        self.categories = CategoryRepository(db)
        self.sync_jobs = SyncJobRepository(db)
        self.event_bus = EventBus(db)

    def run_sync(
        self, *, account_id: uuid.UUID, connector: Connector, idempotency_key: str
    ) -> SyncJob:
        existing = self.sync_jobs.find_active_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        account = self.accounts.get_by_id(account_id)
        if account is None:
            raise NotFoundError("Account not found.")

        # Phase 1: commit a "running" marker in its own short transaction, so
        # an external observer sees real progress even if this worker is
        # later killed mid-sync -- the rest of the work happens in a
        # separate transaction below.
        job = self.sync_jobs.create_running(
            account_id=account_id,
            cursor_before=account.last_sync_cursor,
            idempotency_key=idempotency_key,
        )
        self.db.commit()

        try:
            self._do_sync(account=account, connector=connector, job=job)
        except Exception as exc:
            self.db.rollback()
            self.sync_jobs.mark_failed(job, error_message=str(exc))
            self.db.commit()
            raise

        return job

    def _do_sync(self, *, account: Account, connector: Connector, job: SyncJob) -> None:
        raw_accounts = connector.fetch_accounts()
        raw_transactions, next_cursor = connector.fetch_transactions(
            cursor=account.last_sync_cursor
        )

        result = run_connector_sync_pipeline(
            raw_transactions=raw_transactions,
            user_id=account.user_id,
            account_id=account.id,
            account_currency=account.currency,
            import_source=connector.source,
            import_batch_id=job.id,
            deps=make_pipeline_dependencies(
                transactions=self.transactions,
                merchants=self.merchants,
                categories=self.categories,
                user_id=account.user_id,
                account_id=account.id,
            ),
        )

        self.transactions.bulk_create(result.transactions)
        self.provenance.bulk_create(result.provenance, sync_job_id=job.id)

        reported_account = next(
            (ra for ra in raw_accounts if ra.external_account_id == account.external_account_id),
            raw_accounts[0] if raw_accounts else None,
        )
        reconciliation = reconcile_account_balance(
            starting_balance=account.current_balance,
            transactions=result.transactions,
            reported_current_balance=reported_account.current_balance if reported_account else None,
        )

        if reported_account is not None:
            account.current_balance = reported_account.current_balance
            account.available_balance = reported_account.available_balance
        account.last_sync_cursor = next_cursor

        self.audit_log.record(
            event_type="sync.completed",
            user_id=account.user_id,
            resource_type="account",
            resource_id=account.id,
            metadata={
                "imported_count": result.imported_count,
                "duplicate_count": result.duplicate_count,
                "reconciliation_status": reconciliation.status,
            },
        )

        imported_event = TransactionsImported(
            aggregate_id=account.id,
            transaction_ids=[txn.id for txn in result.transactions],
            imported_count=result.imported_count,
            duplicate_count=result.duplicate_count,
            import_source=connector.source.value,
        )
        self.event_bus.record(imported_event)

        self.sync_jobs.mark_completed(
            job,
            cursor_after=next_cursor,
            reconciliation_status=reconciliation.status,
            discrepancy_amount=reconciliation.discrepancy_amount,
        )

        sync_completed_event = SyncCompleted(
            aggregate_id=job.id,
            account_id=account.id,
            status=SyncJobStatus.COMPLETED.value,
            reconciliation_status=reconciliation.status,
        )
        self.event_bus.record(sync_completed_event)

        self.db.commit()
        self.event_bus.dispatch(imported_event)
        self.event_bus.dispatch(sync_completed_event)
