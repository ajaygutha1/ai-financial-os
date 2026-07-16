import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import add_months, month_start
from app.models.transaction import TransactionType
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.analytics import TaxableEventsResponse

DEFAULT_MONTHS = 12
_TRACKED_TYPES = (
    TransactionType.DIVIDEND.value,
    TransactionType.INTEREST.value,
    TransactionType.BUY.value,
    TransactionType.SELL.value,
)
METHODOLOGY = (
    "Counts and totals dividend, interest, buy, and sell transactions over "
    "the trailing window by transaction_type, across all accounts. This is "
    "a rough signal for potentially taxable activity, not a capital-gains "
    "or cost-basis calculation -- this schema doesn't track tax lots or "
    "cost basis, so buy/sell totals are gross transaction amounts, not "
    "gains. Excludes transfers and flagged duplicates."
)


def compute(
    db: Session, user_id: uuid.UUID, *, months: int = DEFAULT_MONTHS
) -> TaxableEventsResponse:
    as_of = date.today()
    period_start = add_months(month_start(as_of), -(months - 1))
    txns = TransactionRepository(db).list_for_analytics(
        user_id, date_from=period_start, date_to=as_of
    )

    totals: dict[str, Decimal] = dict.fromkeys(_TRACKED_TYPES, Decimal("0"))
    counts: dict[str, int] = dict.fromkeys(_TRACKED_TYPES, 0)
    for t in txns:
        if t.is_duplicate_of is not None or t.is_transfer:
            continue
        if t.transaction_type in totals:
            totals[t.transaction_type] += abs(Decimal(t.amount))
            counts[t.transaction_type] += 1

    return TaxableEventsResponse(
        dividend_total=totals[TransactionType.DIVIDEND.value],
        interest_total=totals[TransactionType.INTEREST.value],
        buy_total=totals[TransactionType.BUY.value],
        sell_total=totals[TransactionType.SELL.value],
        dividend_count=counts[TransactionType.DIVIDEND.value],
        interest_count=counts[TransactionType.INTEREST.value],
        buy_count=counts[TransactionType.BUY.value],
        sell_count=counts[TransactionType.SELL.value],
        period_start=period_start,
        period_end=as_of,
        methodology=METHODOLOGY,
    )
