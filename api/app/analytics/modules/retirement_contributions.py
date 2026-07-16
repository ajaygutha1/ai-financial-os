import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import add_months, month_start
from app.models.account import AccountType
from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.analytics import RetirementContributionsResponse

DEFAULT_MONTHS = 6
METHODOLOGY = (
    "Net monthly contribution = sum of non-transfer, non-duplicate activity "
    "across active retirement accounts, averaged over the trailing window. "
    "Retirement accounts are asset accounts, so a positive amount is money "
    "added or investment growth and a negative amount is a withdrawal -- "
    "same sign convention as checking/savings. This is a cash-flow signal, "
    "not a return-on-investment calculation."
)


def compute(
    db: Session, user_id: uuid.UUID, *, months: int = DEFAULT_MONTHS
) -> RetirementContributionsResponse:
    as_of = date.today()
    period_start = add_months(month_start(as_of), -(months - 1))

    accounts = [
        a
        for a in AccountRepository(db).list_for_user(user_id)
        if a.is_active and a.account_type == AccountType.RETIREMENT.value
    ]
    total_balance = sum((Decimal(a.current_balance) for a in accounts), Decimal("0"))
    if not accounts:
        return RetirementContributionsResponse(
            total_balance=Decimal("0"),
            average_monthly_contribution=Decimal("0"),
            account_count=0,
            months_considered=months,
            methodology=METHODOLOGY,
        )

    account_ids = {a.id for a in accounts}
    txns = TransactionRepository(db).list_for_analytics(
        user_id, date_from=period_start, date_to=as_of
    )
    net_total = Decimal("0")
    for t in txns:
        if t.account_id in account_ids and t.is_duplicate_of is None and not t.is_transfer:
            net_total += Decimal(t.amount)

    return RetirementContributionsResponse(
        total_balance=total_balance,
        average_monthly_contribution=net_total / months,
        account_count=len(accounts),
        months_considered=months,
        methodology=METHODOLOGY,
    )
