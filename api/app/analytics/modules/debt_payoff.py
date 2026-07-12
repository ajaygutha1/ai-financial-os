import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import LIABILITY_ACCOUNT_TYPES, add_months, month_start
from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.analytics import DebtAccountProjection, DebtPayoffResponse

DEFAULT_MONTHS = 6
METHODOLOGY = (
    "For each open credit-card/loan/mortgage account: net monthly paydown = "
    "average(payments/credits - new charges) over the trailing window. Months "
    "to payoff = current balance / net monthly paydown, assuming that rate "
    "holds steady. This is a naive projection -- it doesn't account for "
    "interest accrual (not tracked in this schema yet) or future changes in "
    "spending or payment behavior."
)


def compute(db: Session, user_id: uuid.UUID, *, months: int = DEFAULT_MONTHS) -> DebtPayoffResponse:
    as_of = date.today()
    period_start = add_months(month_start(as_of), -(months - 1))

    accounts = [
        a
        for a in AccountRepository(db).list_for_user(user_id)
        if a.is_active and a.account_type in LIABILITY_ACCOUNT_TYPES
    ]
    if not accounts:
        return DebtPayoffResponse(accounts=[], months_considered=months, methodology=METHODOLOGY)

    account_ids = {a.id for a in accounts}
    txns = TransactionRepository(db).list_for_analytics(
        user_id, date_from=period_start, date_to=as_of
    )
    by_account: dict[uuid.UUID, Decimal] = dict.fromkeys(account_ids, Decimal("0"))
    for t in txns:
        if t.account_id in account_ids and t.is_duplicate_of is None and not t.is_transfer:
            # On a liability account: positive = new charge, negative =
            # payment/credit, so the negated sum is the net paydown.
            by_account[t.account_id] += -Decimal(t.amount)

    projections = []
    for account in accounts:
        net_monthly_paydown = by_account[account.id] / months
        on_track = net_monthly_paydown > 0
        months_to_payoff: Decimal | None = None
        if on_track and account.current_balance > 0:
            months_to_payoff = Decimal(account.current_balance) / net_monthly_paydown

        projections.append(
            DebtAccountProjection(
                account_id=account.id,
                account_name=account.name,
                current_balance=Decimal(account.current_balance),
                net_monthly_paydown=net_monthly_paydown,
                months_to_payoff=months_to_payoff,
                on_track=on_track,
            )
        )

    return DebtPayoffResponse(
        accounts=projections, months_considered=months, methodology=METHODOLOGY
    )
