import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import add_months, cash_flow_transactions, classify_flow, month_start
from app.models.transaction import Transaction
from app.schemas.analytics import CategoryTrend, ExpenseTrendsResponse

DEFAULT_MONTHS = 4
RISING_THRESHOLD = Decimal("0.15")
FALLING_THRESHOLD = Decimal("-0.15")
METHODOLOGY = (
    "Compares each category's most recent month of spend to the average of "
    "the prior months in the window; a change beyond +/-15% is labeled "
    "rising/falling, otherwise steady. A category with no prior spend is "
    "labeled 'new'. Categories come from the merchant-normalization pipeline "
    "(Milestone 2); uncategorized spend is grouped as 'Uncategorized'."
)


def _category_label(txn: Transaction) -> str:
    if txn.category_ref is not None:
        return txn.category_ref.name
    if txn.category:
        return txn.category
    return "Uncategorized"


def compute(
    db: Session, user_id: uuid.UUID, *, months: int = DEFAULT_MONTHS
) -> ExpenseTrendsResponse:
    as_of = date.today()
    period_start = add_months(month_start(as_of), -(months - 1))
    months_sequence = [add_months(period_start, i) for i in range(months)]
    latest_month = months_sequence[-1]
    prior_months = months_sequence[:-1]

    txns = cash_flow_transactions(db, user_id, date_from=period_start, date_to=as_of)

    totals: dict[str, dict[date, Decimal]] = defaultdict(dict)
    for txn in txns:
        _, expense = classify_flow(txn)
        if expense <= 0:
            continue
        label = _category_label(txn)
        bucket = month_start(txn.posted_at)
        totals[label][bucket] = totals[label].get(bucket, Decimal("0")) + expense

    trends: list[CategoryTrend] = []
    for label, by_month in totals.items():
        latest = by_month.get(latest_month, Decimal("0"))
        prior_values = [by_month.get(m, Decimal("0")) for m in prior_months]
        prior_average = (
            sum(prior_values, Decimal("0")) / len(prior_values) if prior_values else Decimal("0")
        )

        change_pct: Decimal | None
        if prior_average == 0:
            trend = "new" if latest > 0 else "steady"
            change_pct = None
        else:
            change_pct = (latest - prior_average) / prior_average
            if change_pct >= RISING_THRESHOLD:
                trend = "rising"
            elif change_pct <= FALLING_THRESHOLD:
                trend = "falling"
            else:
                trend = "steady"

        trends.append(
            CategoryTrend(
                category=label,
                latest_month_total=latest,
                prior_average=prior_average,
                change_pct=change_pct,
                trend=trend,
            )
        )

    trends.sort(key=lambda t: t.latest_month_total, reverse=True)

    return ExpenseTrendsResponse(
        categories=trends,
        period_start=period_start,
        period_end=latest_month,
        methodology=METHODOLOGY,
    )
