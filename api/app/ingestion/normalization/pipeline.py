import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from app.ingestion.normalization.deduplicator import deduplicate
from app.ingestion.normalization.merchant_normalizer import normalize_merchant
from app.ingestion.normalization.parser import ParseError, parse_csv
from app.models.transaction import ImportSource, Transaction, TransactionType


@dataclass
class PipelineResult:
    transactions: list[Transaction]
    imported_count: int
    duplicate_count: int
    error_count: int
    errors: list[str] = field(default_factory=list)


def run_csv_import_pipeline(
    *,
    content: bytes,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    debit_positive: bool,
    existing_lookup: Callable[[Transaction], list[Transaction]],
) -> PipelineResult:
    """Parse -> normalize -> deduplicate. Persistence is the caller's
    responsibility (see CsvImportService) so this function stays a pure,
    independently testable transformation — the same shape every later
    connector (OFX, Plaid, Coinbase) will reuse.
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

    duplicate_count = deduplicate(transactions, existing_lookup=existing_lookup)

    return PipelineResult(
        transactions=transactions,
        imported_count=len(transactions) - duplicate_count,
        duplicate_count=duplicate_count,
        error_count=len(parse_result.errors),
        errors=[_format_error(e) for e in parse_result.errors],
    )


def _format_error(error: ParseError) -> str:
    return f"Row {error.row_number}: {error.message}"
