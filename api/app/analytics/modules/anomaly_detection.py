import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import add_months, cash_flow_transactions, classify_flow, month_start
from app.models.transaction import Transaction
from app.schemas.analytics import AnomalyDetectionResponse, AnomalyFlag

DEFAULT_MONTHS = 3
_DUPLICATE_WINDOW_DAYS = 3
_UNUSUAL_AMOUNT_MULTIPLE = Decimal("3")
_NEW_MERCHANT_MULTIPLE = Decimal("2")
METHODOLOGY = (
    "Three deterministic, rule-based checks over trailing-window "
    "checking/savings/credit-card activity (transfers and flagged "
    "duplicates excluded): (1) possible_duplicate_charge -- two charges at "
    "the same merchant, same account, same amount, within "
    f"{_DUPLICATE_WINDOW_DAYS} days of each other; (2) "
    "unusual_amount_for_category -- a single charge more than "
    f"{_UNUSUAL_AMOUNT_MULTIPLE}x the average of that category's *other* "
    "charges in the window (the charge under review is excluded from its "
    "own baseline, same principle as expense_trends' prior-month average); "
    "(3) new_merchant_large_amount -- the first charge from a merchant in "
    f"the window, above {_NEW_MERCHANT_MULTIPLE}x the user's average charge "
    "size (also excluding itself). This is heuristic pattern-matching for "
    "the user to review, not a fraud determination -- each flag is a "
    "starting point, not a conclusion."
)


def _category_label(txn: Transaction) -> str:
    if txn.category_ref is not None:
        return txn.category_ref.name
    if txn.category:
        return txn.category
    return "Uncategorized"


def compute(
    db: Session, user_id: uuid.UUID, *, months: int = DEFAULT_MONTHS
) -> AnomalyDetectionResponse:
    as_of = date.today()
    period_start = add_months(month_start(as_of), -(months - 1))
    txns = cash_flow_transactions(db, user_id, date_from=period_start, date_to=as_of)

    if not txns:
        return AnomalyDetectionResponse(
            flags=[],
            transactions_scanned=0,
            period_start=period_start,
            period_end=as_of,
            methodology=METHODOLOGY,
        )

    txns_sorted = sorted(txns, key=lambda t: t.posted_at)
    expense_by_txn: dict[uuid.UUID, Decimal] = {}
    category_by_txn: dict[uuid.UUID, str] = {}
    category_sum: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    category_count: dict[str, int] = defaultdict(int)
    for t in txns_sorted:
        _, expense = classify_flow(t)
        if expense <= 0:
            continue
        expense_by_txn[t.id] = expense
        label = _category_label(t)
        category_by_txn[t.id] = label
        category_sum[label] += expense
        category_count[label] += 1

    total_expense = sum(expense_by_txn.values(), Decimal("0"))
    total_count = len(expense_by_txn)

    def leave_one_out_average(total: Decimal, count: int, this_value: Decimal) -> Decimal:
        """Average of every *other* value in the set -- a charge is compared
        against a baseline that excludes itself, so one large charge can't
        inflate the very average it's being measured against."""
        remaining = count - 1
        return (total - this_value) / remaining if remaining > 0 else Decimal("0")

    flags: list[AnomalyFlag] = []
    flagged_ids: set[uuid.UUID] = set()

    # (1) Possible duplicate charges: same account + merchant + amount,
    # close together in time.
    duplicate_groups: dict[tuple[uuid.UUID, str | None, Decimal], list[Transaction]] = defaultdict(
        list
    )
    for t in txns_sorted:
        if t.id not in expense_by_txn or t.merchant_normalized is None:
            continue
        duplicate_groups[(t.account_id, t.merchant_normalized, Decimal(t.amount))].append(t)

    for (_account_id, merchant, amount), group in duplicate_groups.items():
        if len(group) < 2:
            continue
        group_sorted = sorted(group, key=lambda t: t.posted_at)
        for prev, curr in zip(group_sorted, group_sorted[1:], strict=False):
            if (curr.posted_at - prev.posted_at) <= timedelta(days=_DUPLICATE_WINDOW_DAYS):
                for txn in (prev, curr):
                    if txn.id in flagged_ids:
                        continue
                    flags.append(
                        AnomalyFlag(
                            transaction_id=txn.id,
                            posted_at=txn.posted_at,
                            account_name=txn.account.name,
                            merchant=txn.merchant_normalized,
                            amount=Decimal(txn.amount),
                            reason="possible_duplicate_charge",
                            detail=(
                                f"Same amount (${amount}) at {merchant} within "
                                f"{_DUPLICATE_WINDOW_DAYS} days of another charge."
                            ),
                        )
                    )
                    flagged_ids.add(txn.id)

    # Duplicate-flagged transactions must not inflate the baselines the
    # other two checks compare against -- otherwise a large duplicate charge
    # drags the category/user average up enough to hide a genuinely unusual
    # charge that would otherwise have cleared the 3x/2x threshold.
    for flagged_id in flagged_ids:
        flagged_expense = expense_by_txn[flagged_id]
        flagged_label = category_by_txn[flagged_id]
        category_sum[flagged_label] -= flagged_expense
        category_count[flagged_label] -= 1
        total_expense -= flagged_expense
        total_count -= 1

    # (2) Unusual amount for category, and (3) new merchant + large amount --
    # evaluated in chronological order so "new" reflects first appearance
    # within the window, not just within the whole set.
    merchant_first_seen: set[str] = set()
    for t in txns_sorted:
        txn_expense = expense_by_txn.get(t.id)
        if txn_expense is None or t.id in flagged_ids:
            if t.merchant_normalized is not None:
                merchant_first_seen.add(t.merchant_normalized)
            continue

        label = category_by_txn[t.id]
        cat_avg = leave_one_out_average(category_sum[label], category_count[label], txn_expense)
        merchant = t.merchant_normalized
        if cat_avg > 0 and txn_expense > cat_avg * _UNUSUAL_AMOUNT_MULTIPLE:
            flags.append(
                AnomalyFlag(
                    transaction_id=t.id,
                    posted_at=t.posted_at,
                    account_name=t.account.name,
                    merchant=merchant,
                    amount=Decimal(t.amount),
                    reason="unusual_amount_for_category",
                    detail=(
                        f"${txn_expense} is more than {_UNUSUAL_AMOUNT_MULTIPLE}x this "
                        f"category's ({label}) average of ${cat_avg:.2f} in this window."
                    ),
                )
            )
        else:
            user_avg = leave_one_out_average(total_expense, total_count, txn_expense)
            if (
                merchant is not None
                and merchant not in merchant_first_seen
                and user_avg > 0
                and txn_expense > user_avg * _NEW_MERCHANT_MULTIPLE
            ):
                flags.append(
                    AnomalyFlag(
                        transaction_id=t.id,
                        posted_at=t.posted_at,
                        account_name=t.account.name,
                        merchant=merchant,
                        amount=Decimal(t.amount),
                        reason="new_merchant_large_amount",
                        detail=(
                            f"First charge from {merchant} in this window, ${txn_expense} vs. "
                            f"your average charge of ${user_avg:.2f}."
                        ),
                    )
                )

        if merchant is not None:
            merchant_first_seen.add(merchant)

    flags.sort(key=lambda f: f.posted_at, reverse=True)
    return AnomalyDetectionResponse(
        flags=flags,
        transactions_scanned=len(txns),
        period_start=period_start,
        period_end=as_of,
        methodology=METHODOLOGY,
    )
