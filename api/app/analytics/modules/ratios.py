import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import monthly_income_and_expenses
from app.analytics.modules import emergency_fund, net_worth
from app.schemas.analytics import RatiosResponse

DEFAULT_MONTHS = 6
METHODOLOGY = (
    "Liquidity (months of coverage) comes directly from the emergency-fund "
    "module. Debt-to-annual-income annualizes this window's average monthly "
    "income and divides total liability balances (from the net-worth module) "
    "by it. Expense-to-income is average monthly expenses divided by average "
    "monthly income over the same window. All income/expense figures use the "
    "same account-type sign convention as the cash-flow module."
)


def compute(db: Session, user_id: uuid.UUID, *, months: int = DEFAULT_MONTHS) -> RatiosResponse:
    flows = monthly_income_and_expenses(db, user_id, months=months)
    avg_income = sum((f.income for f in flows), Decimal("0")) / len(flows)
    avg_expenses = sum((f.expenses for f in flows), Decimal("0")) / len(flows)

    savings_rate: Decimal | None = None
    expense_to_income_ratio: Decimal | None = None
    debt_to_annual_income: Decimal | None = None

    if avg_income > 0:
        savings_rate = (avg_income - avg_expenses) / avg_income
        expense_to_income_ratio = avg_expenses / avg_income
        annualized_income = avg_income * 12
        nw = net_worth.compute(db, user_id)
        debt_to_annual_income = nw.liabilities_total / annualized_income

    fund = emergency_fund.compute(db, user_id, months=months)

    return RatiosResponse(
        savings_rate=savings_rate,
        expense_to_income_ratio=expense_to_income_ratio,
        liquidity_ratio_months=fund.months_of_coverage,
        debt_to_annual_income=debt_to_annual_income,
        months_considered=months,
        methodology=METHODOLOGY,
    )
