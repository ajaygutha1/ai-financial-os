import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import add_months, monthly_income_and_expenses
from app.analytics.modules import net_worth
from app.schemas.analytics import ForecastMonth, ForecastResponse

DEFAULT_MONTHS = 6
_PROJECTION_MONTHS = 6
METHODOLOGY = (
    "Naive linear projection, not a real forecast model: average monthly net "
    "cash flow over the trailing window is added to current net worth, once "
    f"per month, for the next {_PROJECTION_MONTHS} months. It does not "
    "account for one-off events, seasonal spending, interest/investment "
    "growth, or any change in future behavior -- it's a straight-line "
    "extrapolation of recent history, same category of naive projection as "
    "debt_payoff's payoff estimate."
)


def compute(db: Session, user_id: uuid.UUID, *, months: int = DEFAULT_MONTHS) -> ForecastResponse:
    as_of = date.today()
    flows = monthly_income_and_expenses(db, user_id, months=months, as_of=as_of)
    total_net = sum((f.net for f in flows), Decimal("0"))
    average_monthly_net = total_net / months

    current_net_worth = net_worth.compute(db, user_id).net_worth

    projected_months = []
    running = current_net_worth
    this_month = flows[-1].month
    for i in range(1, _PROJECTION_MONTHS + 1):
        running += average_monthly_net
        projected_months.append(
            ForecastMonth(month=add_months(this_month, i), projected_net_worth=running)
        )

    return ForecastResponse(
        current_net_worth=current_net_worth,
        average_monthly_net=average_monthly_net,
        months_considered=months,
        projected_months=projected_months,
        methodology=METHODOLOGY,
    )
