import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.normalization.pipeline import ProvenanceEntry
from app.models.transaction_provenance import TransactionProvenance


class TransactionProvenanceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_transaction(self, transaction_id: uuid.UUID) -> list[TransactionProvenance]:
        stmt = (
            select(TransactionProvenance)
            .where(TransactionProvenance.transaction_id == transaction_id)
            .order_by(TransactionProvenance.created_at)
        )
        return list(self.db.scalars(stmt))

    def bulk_create(
        self, entries: list[ProvenanceEntry], *, sync_job_id: uuid.UUID | None = None
    ) -> None:
        if not entries:
            return
        rows = [
            TransactionProvenance(
                transaction_id=entry.transaction_id,
                sync_job_id=sync_job_id,
                step=entry.step,
                detail=entry.detail,
            )
            for entry in entries
        ]
        self.db.add_all(rows)
        self.db.flush()
