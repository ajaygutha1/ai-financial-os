from collections.abc import Callable

from app.models.transaction import Transaction, TransactionType


def detect_transfers(
    transactions: list[Transaction],
    *,
    find_transfer_match: Callable[[Transaction], Transaction | None],
) -> list[tuple[Transaction, Transaction]]:
    """Flags transactions that are transfers between the user's own accounts
    (an equal-and-opposite counterpart already persisted in a different
    account) by setting `is_transfer` and `transaction_type`. Skips rows
    already dropped as hard-identity duplicates -- there's nothing to detect
    on a row that isn't going to be persisted. Returns the matched pairs so
    the caller can record provenance.
    """
    matches: list[tuple[Transaction, Transaction]] = []

    for txn in transactions:
        if txn.is_duplicate_of is not None:
            continue

        match = find_transfer_match(txn)
        if match is None:
            continue

        txn.is_transfer = True
        txn.transaction_type = TransactionType.TRANSFER.value
        matches.append((txn, match))

    return matches
