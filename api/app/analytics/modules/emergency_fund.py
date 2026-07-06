import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import liquid_assets_total, monthly_income_and_expenses
from app.schemas.analytics import EmergencyFundResponse

DEFAULT_MONTHS = 3
METHODOLOGY = (
    "Liquid assets (checking + savings balances) divided by the average of "
    "the trailing months' total expenses. This product doesn't yet "
    "distinguish essential from discretionary spending, so using total "
    "expenses is a conservative (lower) estimate of true runway."
)

# Standard personal-finance guidance targets 3-6 months of coverage; below 1
# month is treated as critical.
CRITICAL_MONTHS = Decimal("1")
LOW_MONTHS = Decimal("3")
ADEQUATE_MONTHS = Decimal("6")


def _tier(months_covered: Decimal | None) -> str:
    if months_covered is None:
        return "unknown"
    if months_covered < CRITICAL_MONTHS:
        return "critical"
    if months_covered < LOW_MONTHS:
        return "low"
    if months_covered < ADEQUATE_MONTHS:
        return "adequate"
    return "strong"


def compute(
    db: Session, user_id: uuid.UUID, *, months: int = DEFAULT_MONTHS
) -> EmergencyFundResponse:
    liquid = liquid_assets_total(db, user_id)
    flows = monthly_income_and_expenses(db, user_id, months=months)
    average_monthly_expenses = sum((f.expenses for f in flows), Decimal("0")) / len(flows)

    months_covered: Decimal | None = None
    if average_monthly_expenses > 0:
        months_covered = liquid / average_monthly_expenses

    return EmergencyFundResponse(
        liquid_assets=liquid,
        average_monthly_expenses=average_monthly_expenses,
        months_of_coverage=months_covered,
        health_tier=_tier(months_covered),
        methodology=METHODOLOGY,
    )
