import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.events.event_bus import EventBus
from app.ingestion.connectors.ofx import OfxConnector
from app.ingestion.normalization.pipeline import run_connector_sync_pipeline
from app.models.transaction import ImportSource
from app.repositories.account_repository import AccountRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.merchant_repository import MerchantRepository
from app.repositories.transaction_provenance_repository import TransactionProvenanceRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.imports import ImportResult
from app.services.ingestion_common import make_pipeline_dependencies, persist_pipeline_result


class OfxImportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounts = AccountRepository(db)
        self.transactions = TransactionRepository(db)
        self.provenance = TransactionProvenanceRepository(db)
        self.audit_log = AuditLogRepository(db)
        self.merchants = MerchantRepository(db)
        self.categories = CategoryRepository(db)
        self.event_bus = EventBus(db)

    def import_ofx(
        self, *, user_id: uuid.UUID, account_id: uuid.UUID, content: bytes
    ) -> ImportResult:
        account = self.accounts.get_by_id(account_id)
        if account is None or account.user_id != user_id:
            raise NotFoundError("Account not found.")

        connector = OfxConnector(content)
        raw_transactions, _ = connector.fetch_transactions(
            cursor=None, external_account_id=account.external_account_id
        )

        result = run_connector_sync_pipeline(
            raw_transactions=raw_transactions,
            user_id=user_id,
            account_id=account_id,
            account_currency=account.currency,
            import_source=ImportSource.OFX,
            import_batch_id=uuid.uuid4(),
            deps=make_pipeline_dependencies(
                transactions=self.transactions,
                merchants=self.merchants,
                categories=self.categories,
                user_id=user_id,
                account_id=account_id,
            ),
        )

        event = persist_pipeline_result(
            transactions=self.transactions,
            provenance=self.provenance,
            audit_log=self.audit_log,
            event_bus=self.event_bus,
            result=result,
            user_id=user_id,
            account_id=account_id,
            event_type="ofx_import.completed",
            import_source=ImportSource.OFX.value,
        )
        self.db.commit()
        self.event_bus.dispatch(event)

        return ImportResult(
            imported_count=result.imported_count,
            duplicate_count=result.duplicate_count,
            error_count=result.error_count,
            errors=result.errors,
        )
