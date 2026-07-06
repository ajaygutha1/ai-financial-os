import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import monthly_income_and_expenses
from app.schemas.analytics import BurnRateResponse

DEFAULT_MONTHS = 3
METHODOLOGY = (
    "Average of (expenses - income) per month over the trailing window, using "
    "the same checking/savings/credit-card classification as the cash-flow "
    "module. Positive means spending more than coming in (burning savings); "
    "negative means net saving."
)


def compute(db: Session, user_id: uuid.UUID, *, months: int = DEFAULT_MONTHS) -> BurnRateResponse:
    flows = monthly_income_and_expenses(db, user_id, months=months)
    monthly_net_burn = [f.expenses - f.income for f in flows]
    average = sum(monthly_net_burn, Decimal("0")) / len(monthly_net_burn)

    return BurnRateResponse(
        average_monthly_burn=average,
        is_burning=average > 0,
        months_considered=months,
        period_start=flows[0].month,
        period_end=flows[-1].month,
        methodology=METHODOLOGY,
    )
