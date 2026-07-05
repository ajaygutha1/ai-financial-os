from dataclasses import dataclass
from decimal import Decimal

from app.models.sync_job import ReconciliationStatus
from app.models.transaction import Transaction

# A peer of analytics/modules/ (the M3 stub package), not inside it --
# reconciliation is an integrity check, not a financial metric, but lives in
# the same top-level module since it's the same category of "compute
# something about the numbers" concern.

DEFAULT_TOLERANCE = Decimal("0.01")


@dataclass
class ReconciliationResult:
    status: str
    discrepancy_amount: Decimal | None


def reconcile_account_balance(
    *,
    starting_balance: Decimal,
    transactions: list[Transaction],
    reported_current_balance: Decimal | None,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> ReconciliationResult:
    """Verifies `starting_balance + sum(transactions) == reported_current_balance`
    within a small tolerance (for floating-point-ish rounding noise from
    upstream sources, not our own storage -- our own amounts are exact
    Decimals). Only meaningful for connector-driven syncs, which have a
    connector-reported balance to check against; CSV/OFX imports have none,
    so callers there should not call this at all.
    """
    if reported_current_balance is None:
        return ReconciliationResult(
            status=ReconciliationStatus.SKIPPED.value, discrepancy_amount=None
        )

    total = sum(
        (txn.amount for txn in transactions if txn.is_duplicate_of is None),
        Decimal("0"),
    )
    discrepancy = (starting_balance + total) - reported_current_balance

    if abs(discrepancy) <= tolerance:
        return ReconciliationResult(
            status=ReconciliationStatus.MATCHED.value, discrepancy_amount=None
        )
    return ReconciliationResult(
        status=ReconciliationStatus.DISCREPANCY.value, discrepancy_amount=discrepancy
    )
