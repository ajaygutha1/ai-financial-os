import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.ingestion.normalization.pipeline import run_csv_import_pipeline
from app.repositories.account_repository import AccountRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.csv_import import CsvImportResult


class CsvImportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounts = AccountRepository(db)
        self.transactions = TransactionRepository(db)
        self.audit_log = AuditLogRepository(db)

    def import_csv(
        self,
        *,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        content: bytes,
        debit_positive: bool,
    ) -> CsvImportResult:
        account = self.accounts.get_by_id(account_id)
        if account is None or account.user_id != user_id:
            raise NotFoundError("Account not found.")

        result = run_csv_import_pipeline(
            content=content,
            user_id=user_id,
            account_id=account_id,
            debit_positive=debit_positive,
            existing_lookup=lambda txn: self.transactions.find_duplicate_candidates(
                account_id=txn.account_id,
                posted_at=txn.posted_at,
                amount=txn.amount,
                merchant_normalized=txn.merchant_normalized,
            ),
        )

        self.transactions.bulk_create(result.transactions)
        self.audit_log.record(
            event_type="csv_import.completed",
            user_id=user_id,
            resource_type="account",
            resource_id=account_id,
            metadata={
                "imported_count": result.imported_count,
                "duplicate_count": result.duplicate_count,
                "error_count": result.error_count,
            },
        )
        self.db.commit()

        return CsvImportResult(
            imported_count=result.imported_count,
            duplicate_count=result.duplicate_count,
            error_count=result.error_count,
            errors=result.errors,
        )
