import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sync_job import SyncJob, SyncJobStatus


class SyncJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_active_by_idempotency_key(self, idempotency_key: str) -> SyncJob | None:
        """'Active' mirrors the partial unique index on sync_job: any row
        whose status isn't 'failed'. A match means either a sync is already
        running or has already completed for this exact (account, cursor)
        combination -- either way, there's nothing new to do.
        """
        stmt = select(SyncJob).where(
            SyncJob.idempotency_key == idempotency_key,
            SyncJob.status != SyncJobStatus.FAILED.value,
        )
        return self.db.scalar(stmt)

    def create_running(
        self, *, account_id: uuid.UUID, cursor_before: str | None, idempotency_key: str
    ) -> SyncJob:
        job = SyncJob(
            id=uuid.uuid4(),
            account_id=account_id,
            status=SyncJobStatus.RUNNING.value,
            cursor_before=cursor_before,
            idempotency_key=idempotency_key,
        )
        self.db.add(job)
        self.db.flush()
        return job

    def mark_completed(
        self,
        job: SyncJob,
        *,
        cursor_after: str | None,
        reconciliation_status: str,
        discrepancy_amount: Decimal | None,
    ) -> None:
        job.status = SyncJobStatus.COMPLETED.value
        job.finished_at = datetime.now(UTC)
        job.cursor_after = cursor_after
        job.reconciliation_status = reconciliation_status
        job.discrepancy_amount = discrepancy_amount

    def mark_failed(self, job: SyncJob, *, error_message: str) -> None:
        job.status = SyncJobStatus.FAILED.value
        job.finished_at = datetime.now(UTC)
        job.error_message = error_message
