import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import monthly_income_and_expenses
from app.schemas.analytics import CashFlowMonth, CashFlowResponse

DEFAULT_MONTHS = 6
METHODOLOGY = (
    "Income = inflows to checking/savings accounts; expenses = outflows from "
    "checking/savings plus net new charges on credit cards. Transfers between "
    "your own accounts and flagged duplicate transactions are excluded. See "
    "app.analytics.common for the full account-type sign convention."
)


def compute(db: Session, user_id: uuid.UUID, *, months: int = DEFAULT_MONTHS) -> CashFlowResponse:
    flows = monthly_income_and_expenses(db, user_id, months=months)
    by_month = [
        CashFlowMonth(
            month=f.month,
            income=f.income,
            expenses=f.expenses,
            net=f.net,
            transaction_count=f.transaction_count,
        )
        for f in flows
    ]
    total_income = sum((f.income for f in flows), Decimal("0"))
    total_expenses = sum((f.expenses for f in flows), Decimal("0"))

    return CashFlowResponse(
        months=by_month,
        total_income=total_income,
        total_expenses=total_expenses,
        net=total_income - total_expenses,
        period_start=flows[0].month,
        period_end=flows[-1].month,
        methodology=METHODOLOGY,
    )
