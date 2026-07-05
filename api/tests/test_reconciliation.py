import uuid
from datetime import date
from decimal import Decimal

from app.analytics.reconciliation import reconcile_account_balance
from app.models.sync_job import ReconciliationStatus
from app.models.transaction import Transaction


def _txn(amount: Decimal, *, is_duplicate_of: uuid.UUID | None = None) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        posted_at=date.today(),
        amount=amount,
        is_duplicate_of=is_duplicate_of,
    )


def test_matched_within_tolerance() -> None:
    result = reconcile_account_balance(
        starting_balance=Decimal("100.00"),
        transactions=[_txn(Decimal("-20.00")), _txn(Decimal("5.00"))],
        reported_current_balance=Decimal("85.00"),
    )
    assert result.status == ReconciliationStatus.MATCHED.value
    assert result.discrepancy_amount is None


def test_discrepancy_outside_tolerance() -> None:
    result = reconcile_account_balance(
        starting_balance=Decimal("100.00"),
        transactions=[_txn(Decimal("-20.00"))],
        reported_current_balance=Decimal("50.00"),
    )
    assert result.status == ReconciliationStatus.DISCREPANCY.value
    assert result.discrepancy_amount == Decimal("30.00")


def test_skipped_when_no_reported_balance() -> None:
    result = reconcile_account_balance(
        starting_balance=Decimal("100.00"), transactions=[], reported_current_balance=None
    )
    assert result.status == ReconciliationStatus.SKIPPED.value
    assert result.discrepancy_amount is None


def test_duplicate_transactions_excluded_from_total() -> None:
    result = reconcile_account_balance(
        starting_balance=Decimal("0"),
        transactions=[
            _txn(Decimal("-50.00"), is_duplicate_of=uuid.uuid4()),
            _txn(Decimal("-10.00")),
        ],
        reported_current_balance=Decimal("-10.00"),
    )
    assert result.status == ReconciliationStatus.MATCHED.value


def test_within_exact_tolerance_boundary_matches() -> None:
    result = reconcile_account_balance(
        starting_balance=Decimal("0"),
        transactions=[_txn(Decimal("-10.00"))],
        reported_current_balance=Decimal("-10.01"),
        tolerance=Decimal("0.01"),
    )
    assert result.status == ReconciliationStatus.MATCHED.value
