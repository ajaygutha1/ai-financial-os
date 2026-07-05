from collections.abc import Callable
from decimal import Decimal

from app.models.transaction import Transaction, TransactionType


def detect_refunds(
    transactions: list[Transaction],
    *,
    find_refund_match: Callable[[Transaction], Transaction | None],
) -> list[tuple[Transaction, Transaction]]:
    """Flags transactions that are refunds of an earlier purchase from the
    same merchant in the same account (an equal-and-opposite inflow within a
    longer window than transfer/dedup matching, since refunds can take
    weeks). Only considers inflows with a resolved merchant -- there's
    nothing to match a refund against otherwise. Returns matched pairs so
    the caller can record provenance.
    """
    matches: list[tuple[Transaction, Transaction]] = []

    for txn in transactions:
        if txn.is_duplicate_of is not None or txn.is_transfer:
            continue
        if txn.amount <= Decimal("0") or not txn.merchant_normalized:
            continue

        match = find_refund_match(txn)
        if match is None:
            continue

        txn.transaction_type = TransactionType.REFUND.value
        matches.append((txn, match))

    return matches
