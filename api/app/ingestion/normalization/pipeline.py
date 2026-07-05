import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.ingestion.connectors.base import RawTransaction
from app.ingestion.normalization.currency_converter import convert_to_account_currency
from app.ingestion.normalization.deduplicator import deduplicate
from app.ingestion.normalization.merchant_normalizer import normalize_merchant
from app.ingestion.normalization.parser import ParseError, parse_csv
from app.ingestion.normalization.payment_classifier import classify_payment_channel
from app.ingestion.normalization.refund_matcher import detect_refunds
from app.ingestion.normalization.transfer_detector import detect_transfers
from app.models.transaction import ImportSource, Transaction, TransactionType


@dataclass
class ProvenanceEntry:
    transaction_id: uuid.UUID
    step: str
    detail: dict[str, Any] | None = None


@dataclass
class PipelineResult:
    transactions: list[Transaction]
    imported_count: int
    duplicate_count: int
    error_count: int
    errors: list[str] = field(default_factory=list)
    provenance: list[ProvenanceEntry] = field(default_factory=list)


@dataclass
class PipelineDependencies:
    """Bundles the DB-backed lookups the normalization core needs. Every
    ingestion source (CSV, OFX, and later the Celery-driven connector sync)
    supplies these the same way -- one dependency object instead of an
    ever-growing list of individual callback parameters.
    """

    existing_lookup: Callable[[Transaction], list[Transaction]]
    resolve_merchant: Callable[[str], tuple[uuid.UUID | None, uuid.UUID | None]]
    find_transfer_match: Callable[[Transaction], Transaction | None]
    find_refund_match: Callable[[Transaction], Transaction | None]


def run_csv_import_pipeline(
    *,
    content: bytes,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    account_currency: str,
    debit_positive: bool,
    deps: PipelineDependencies,
) -> PipelineResult:
    """Parse -> normalize -> deduplicate. Persistence is the caller's
    responsibility (see CsvImportService) so this function stays a pure,
    independently testable transformation.
    """
    parse_result = parse_csv(content, debit_positive=debit_positive)
    import_batch_id = uuid.uuid4()

    transactions: list[Transaction] = []
    for row in parse_result.rows:
        merchant_normalized = normalize_merchant(row.description) or None
        transactions.append(
            Transaction(
                id=uuid.uuid4(),
                user_id=user_id,
                account_id=account_id,
                posted_at=row.posted_at,
                amount=row.amount,
                merchant_raw=row.description or None,
                merchant_normalized=merchant_normalized,
                description=row.description or None,
                transaction_type=TransactionType.PURCHASE.value,
                import_source=ImportSource.CSV.value,
                import_batch_id=import_batch_id,
                raw_payload=row.raw_row,
            )
        )

    persistable, duplicate_count, provenance = _run_normalization_engine(
        transactions, account_currency=account_currency, deps=deps
    )

    return PipelineResult(
        transactions=persistable,
        imported_count=len(transactions) - duplicate_count,
        duplicate_count=duplicate_count,
        error_count=len(parse_result.errors),
        errors=[_format_error(e) for e in parse_result.errors],
        provenance=provenance,
    )


def run_connector_sync_pipeline(
    *,
    raw_transactions: list[RawTransaction],
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    account_currency: str,
    import_source: ImportSource,
    import_batch_id: uuid.UUID,
    deps: PipelineDependencies,
) -> PipelineResult:
    """The connector-driven counterpart to `run_csv_import_pipeline`. Shares
    the same normalization core -- CSV's own parsing/sign-convention step is
    CSV-specific, but every source shares the same normalization core, so
    currency conversion / transfer detection / dedup apply uniformly
    regardless of where a transaction came from.
    """
    transactions: list[Transaction] = []
    for raw in raw_transactions:
        merchant_normalized = normalize_merchant(raw.merchant_raw or raw.description) or None
        transactions.append(
            Transaction(
                id=uuid.uuid4(),
                user_id=user_id,
                account_id=account_id,
                posted_at=raw.posted_at,
                amount=raw.amount,
                currency=raw.currency,
                merchant_raw=raw.merchant_raw or raw.description or None,
                merchant_normalized=merchant_normalized,
                description=raw.description or None,
                transaction_type=TransactionType.PURCHASE.value,
                import_source=import_source.value,
                import_batch_id=import_batch_id,
                external_transaction_id=raw.external_transaction_id,
                raw_payload=raw.raw,
            )
        )

    persistable, duplicate_count, provenance = _run_normalization_engine(
        transactions, account_currency=account_currency, deps=deps
    )

    return PipelineResult(
        transactions=persistable,
        imported_count=len(transactions) - duplicate_count,
        duplicate_count=duplicate_count,
        error_count=0,
        provenance=provenance,
    )


def _run_normalization_engine(
    transactions: list[Transaction],
    *,
    account_currency: str,
    deps: PipelineDependencies,
) -> tuple[list[Transaction], int, list[ProvenanceEntry]]:
    """Shared core between every ingestion source. In order:

    1. Deduplicate (within-batch + against existing data).
    2. Drop hard-identity duplicates from the persist batch (see note below);
       everything past this point only considers `persistable` rows, since
       transaction_provenance.transaction_id is a real FK -- a row that's
       never inserted can't be referenced by a provenance entry either.
    3. Resolve Merchant/Category (dual-write alongside the plain strings --
       see migration 0002's expand/contract note).
    4. Detect transfers (exact cross-account match against already-persisted
       data), then refunds (exact same-merchant match), then fall back to
       ACH/wire text classification for transactions neither matched --
       ordered from strongest to weakest signal so a stronger match always
       wins.
    5. Compute an informational currency-converted amount when the
       transaction's currency differs from the account's.

    Two different duplicate outcomes are possible depending on whether the
    source can supply a real `external_transaction_id`:

    - Heuristic duplicates (CSV -- no external_transaction_id, matched by a
      hash + fuzzy date window) are still persisted with `is_duplicate_of`
      set, so a human can review what was flagged rather than losing the row.
    - Hard-identity duplicates (connectors -- matched by a real
      external_transaction_id) are dropped from the persist batch entirely.
      The partial unique index on (account_id, external_transaction_id) would
      reject a re-insert anyway, and there's nothing new to learn by trying:
      it's certainly the same transaction the connector already reported.
    """
    duplicate_count = deduplicate(transactions, existing_lookup=deps.existing_lookup)

    persistable = [
        txn
        for txn in transactions
        if not (txn.is_duplicate_of is not None and txn.external_transaction_id is not None)
    ]
    persistable_ids = {txn.id for txn in persistable}

    provenance: list[ProvenanceEntry] = []

    for txn in transactions:
        if txn.id not in persistable_ids:
            continue
        if txn.merchant_normalized:
            provenance.append(
                ProvenanceEntry(
                    transaction_id=txn.id,
                    step="merchant_normalized",
                    detail={"merchant_normalized": txn.merchant_normalized},
                )
            )
            merchant_id, category_id = deps.resolve_merchant(txn.merchant_normalized)
            txn.merchant_id = merchant_id
            txn.category_id = category_id
            if merchant_id is not None:
                provenance.append(
                    ProvenanceEntry(
                        transaction_id=txn.id,
                        step="merchant_resolved",
                        detail={
                            "merchant_id": str(merchant_id),
                            "category_id": str(category_id) if category_id else None,
                        },
                    )
                )

    for txn in transactions:
        if txn.is_duplicate_of is not None and txn.id in persistable_ids:
            provenance.append(
                ProvenanceEntry(
                    transaction_id=txn.id,
                    step="duplicate_flagged",
                    detail={"is_duplicate_of": str(txn.is_duplicate_of)},
                )
            )

    transfer_matches = detect_transfers(persistable, find_transfer_match=deps.find_transfer_match)
    for txn, match in transfer_matches:
        provenance.append(
            ProvenanceEntry(
                transaction_id=txn.id,
                step="transfer_detected",
                detail={"matched_transaction_id": str(match.id)},
            )
        )

    refund_matches = detect_refunds(persistable, find_refund_match=deps.find_refund_match)
    for txn, match in refund_matches:
        provenance.append(
            ProvenanceEntry(
                transaction_id=txn.id,
                step="refund_detected",
                detail={"matched_transaction_id": str(match.id)},
            )
        )

    already_classified_ids = {txn.id for txn, _ in transfer_matches} | {
        txn.id for txn, _ in refund_matches
    }
    for txn in persistable:
        if txn.id in already_classified_ids or not txn.description:
            continue
        channel = classify_payment_channel(txn.description)
        if channel is None:
            continue
        txn.transaction_type = TransactionType.TRANSFER.value
        txn.is_transfer = True
        provenance.append(
            ProvenanceEntry(
                transaction_id=txn.id,
                step="ach_wire_classified",
                detail={"channel": channel},
            )
        )

    for txn in persistable:
        if txn.currency == account_currency:
            continue
        converted = convert_to_account_currency(
            amount=txn.amount, from_currency=txn.currency, to_currency=account_currency
        )
        provenance.append(
            ProvenanceEntry(
                transaction_id=txn.id,
                step="currency_converted",
                detail={
                    "original_amount": str(txn.amount),
                    "original_currency": txn.currency,
                    "converted_amount": str(converted) if converted is not None else None,
                    "converted_currency": account_currency,
                    "conversion_available": converted is not None,
                },
            )
        )

    return persistable, duplicate_count, provenance


def _format_error(error: ParseError) -> str:
    return f"Row {error.row_number}: {error.message}"
