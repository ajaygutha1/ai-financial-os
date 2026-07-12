import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import monthly_income_and_expenses
from app.schemas.analytics import SavingsRateMonth, SavingsRateResponse

DEFAULT_MONTHS = 6
METHODOLOGY = (
    "For each month with recorded income, (income - expenses) / income. Months "
    "with no recorded income are excluded from the average (a rate is "
    "undefined without a denominator) but still appear in the monthly "
    "breakdown with a null rate."
)


def compute(
    db: Session, user_id: uuid.UUID, *, months: int = DEFAULT_MONTHS
) -> SavingsRateResponse:
    flows = monthly_income_and_expenses(db, user_id, months=months)
    monthly: list[SavingsRateMonth] = []
    rates: list[Decimal] = []

    for f in flows:
        rate: Decimal | None = None
        if f.income > 0:
            rate = (f.income - f.expenses) / f.income
            rates.append(rate)
        monthly.append(
            SavingsRateMonth(month=f.month, income=f.income, expenses=f.expenses, savings_rate=rate)
        )

    average_rate = sum(rates, Decimal("0")) / len(rates) if rates else None

    return SavingsRateResponse(
        months=monthly,
        average_savings_rate=average_rate,
        months_with_income=len(rates),
        period_start=flows[0].month,
        period_end=flows[-1].month,
        methodology=METHODOLOGY,
    )
