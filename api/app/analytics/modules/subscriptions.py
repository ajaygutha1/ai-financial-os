import statistics
import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import add_months, cash_flow_transactions, classify_flow, month_start
from app.schemas.analytics import DetectedSubscription, SubscriptionsResponse

DEFAULT_MONTHS = 6
MIN_OCCURRENCES = 2
AMOUNT_TOLERANCE_PCT = Decimal("0.10")
CADENCE_WINDOWS_DAYS = {
    "weekly": (6, 8),
    "monthly": (27, 33),
    "annual": (355, 375),
}
METHODOLOGY = (
    f"Groups expense transactions by merchant within the trailing "
    f"{DEFAULT_MONTHS} months; a merchant with at least {MIN_OCCURRENCES} "
    "charges whose intervals cluster around a weekly/monthly/annual cadence "
    "and whose amounts stay within 10% of their average is flagged as a "
    "likely subscription. Rule-based, not a guarantee -- irregular but "
    "genuinely recurring bills may be missed, and coincidental repeat "
    "purchases may be flagged."
)


def _cadence_for(avg_interval_days: float) -> str | None:
    for name, (low, high) in CADENCE_WINDOWS_DAYS.items():
        if low <= avg_interval_days <= high:
            return name
    return None


def compute(
    db: Session, user_id: uuid.UUID, *, months: int = DEFAULT_MONTHS
) -> SubscriptionsResponse:
    as_of = date.today()
    period_start = add_months(month_start(as_of), -(months - 1))
    txns = cash_flow_transactions(db, user_id, date_from=period_start, date_to=as_of)

    by_merchant: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
    for txn in txns:
        if not txn.merchant_normalized:
            continue
        _, expense = classify_flow(txn)
        if expense <= 0:
            continue
        by_merchant[txn.merchant_normalized].append((txn.posted_at, expense))

    detected: list[DetectedSubscription] = []
    for merchant, occurrences in by_merchant.items():
        if len(occurrences) < MIN_OCCURRENCES:
            continue
        occurrences.sort(key=lambda o: o[0])
        dates = [o[0] for o in occurrences]
        amounts = [o[1] for o in occurrences]

        intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        avg_interval = statistics.mean(intervals)
        cadence = _cadence_for(avg_interval)
        if cadence is None:
            continue

        avg_amount = sum(amounts, Decimal("0")) / len(amounts)
        if avg_amount == 0:
            continue
        max_deviation = max(abs(a - avg_amount) / avg_amount for a in amounts)
        if max_deviation > AMOUNT_TOLERANCE_PCT:
            continue

        detected.append(
            DetectedSubscription(
                merchant=merchant,
                cadence=cadence,
                average_amount=avg_amount,
                occurrences=len(occurrences),
                last_charge_date=dates[-1],
                next_expected_date=dates[-1] + timedelta(days=round(avg_interval)),
            )
        )

    detected.sort(key=lambda s: s.average_amount, reverse=True)
    estimated_monthly_total = sum(
        (s.average_amount for s in detected if s.cadence == "monthly"), Decimal("0")
    )

    return SubscriptionsResponse(
        subscriptions=detected,
        estimated_monthly_total=estimated_monthly_total,
        period_start=period_start,
        period_end=as_of,
        methodology=METHODOLOGY,
    )
