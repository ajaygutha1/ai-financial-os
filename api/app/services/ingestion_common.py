import uuid
from collections.abc import Callable

from app.events.domain_event import TransactionsImported
from app.events.event_bus import EventBus
from app.ingestion.normalization.merchant_category_map import KNOWN_MERCHANT_CATEGORIES
from app.ingestion.normalization.pipeline import PipelineDependencies, PipelineResult
from app.models.transaction import Transaction
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.merchant_repository import MerchantRepository
from app.repositories.transaction_provenance_repository import TransactionProvenanceRepository
from app.repositories.transaction_repository import TransactionRepository

# Shared persistence tail for every ingestion source (CSV, OFX, and later the
# Celery-driven connector sync) -- each source's pipeline differs, but what
# happens to a PipelineResult once it exists is identical.


def make_merchant_resolver(
    merchant_repo: MerchantRepository, category_repo: CategoryRepository
) -> Callable[[str], tuple[uuid.UUID | None, uuid.UUID | None]]:
    """Builds the callback the normalization pipeline uses to resolve a
    `merchant_normalized` string into (merchant_id, category_id), find-or-
    creating the `Merchant` row and its default category (from the small
    hand-authored KNOWN_MERCHANT_CATEGORIES map) as needed.
    """

    def resolve(merchant_normalized: str) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        category_name = KNOWN_MERCHANT_CATEGORIES.get(merchant_normalized)
        category_id = category_repo.get_or_create(category_name).id if category_name else None
        merchant = merchant_repo.find_or_create_by_canonical_name(
            merchant_normalized, category_id=category_id
        )
        # Prefer a category already assigned to an existing merchant record
        # over a fresh lookup from the known-merchant map.
        return merchant.id, merchant.category_id

    return resolve


def make_pipeline_dependencies(
    *,
    transactions: TransactionRepository,
    merchants: MerchantRepository,
    categories: CategoryRepository,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> PipelineDependencies:
    """Wires every ingestion source's repository-backed lookups into the one
    dependency bundle the normalization pipeline expects."""

    def find_transfer_match(txn: Transaction) -> Transaction | None:
        return transactions.find_transfer_match(
            user_id=user_id,
            exclude_account_id=account_id,
            posted_at=txn.posted_at,
            amount=txn.amount,
        )

    def find_refund_match(txn: Transaction) -> Transaction | None:
        return transactions.find_refund_match(
            account_id=account_id,
            merchant_normalized=txn.merchant_normalized,
            posted_at=txn.posted_at,
            amount=txn.amount,
        )

    return PipelineDependencies(
        existing_lookup=lambda txn: transactions.find_duplicate_candidates(
            account_id=txn.account_id,
            posted_at=txn.posted_at,
            amount=txn.amount,
            merchant_normalized=txn.merchant_normalized,
        ),
        resolve_merchant=make_merchant_resolver(merchants, categories),
        find_transfer_match=find_transfer_match,
        find_refund_match=find_refund_match,
    )


def persist_pipeline_result(
    *,
    transactions: TransactionRepository,
    provenance: TransactionProvenanceRepository,
    audit_log: AuditLogRepository,
    event_bus: EventBus,
    result: PipelineResult,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    event_type: str,
    import_source: str,
    sync_job_id: uuid.UUID | None = None,
) -> TransactionsImported:
    transactions.bulk_create(result.transactions)
    provenance.bulk_create(result.provenance, sync_job_id=sync_job_id)
    audit_log.record(
        event_type=event_type,
        user_id=user_id,
        resource_type="account",
        resource_id=account_id,
        metadata={
            "imported_count": result.imported_count,
            "duplicate_count": result.duplicate_count,
            "error_count": result.error_count,
        },
    )

    event = TransactionsImported(
        aggregate_id=account_id,
        user_id=user_id,
        transaction_ids=[txn.id for txn in result.transactions],
        imported_count=result.imported_count,
        duplicate_count=result.duplicate_count,
        import_source=import_source,
    )
    event_bus.record(event)
    return event
