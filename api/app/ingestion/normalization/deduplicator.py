from collections.abc import Callable

from app.models.transaction import Transaction

DedupKey = tuple[object, object, object, str | None]


def _dedup_key(txn: Transaction) -> DedupKey:
    return (txn.account_id, txn.posted_at, txn.amount, txn.merchant_normalized)


def deduplicate(
    transactions: list[Transaction],
    *,
    existing_lookup: Callable[[Transaction], list[Transaction]],
) -> int:
    """Flags duplicates via `is_duplicate_of` rather than dropping them, so the
    user can review what was excluded from analytics. Checks two levels:
    exact-key matches within the current batch, then a fuzzy date-window
    lookup against previously persisted transactions (`existing_lookup`,
    typically TransactionRepository.find_duplicate_candidates).
    """
    seen: dict[DedupKey, Transaction] = {}
    duplicate_count = 0

    for txn in transactions:
        key = _dedup_key(txn)
        first_seen = seen.get(key)
        if first_seen is not None:
            txn.is_duplicate_of = first_seen.id
            duplicate_count += 1
            continue

        existing_matches = existing_lookup(txn)
        if existing_matches:
            txn.is_duplicate_of = existing_matches[0].id
            duplicate_count += 1
            continue

        seen[key] = txn

    return duplicate_count
