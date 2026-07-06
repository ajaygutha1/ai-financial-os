import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.analytics.common import LIABILITY_ACCOUNT_TYPES
from app.repositories.account_repository import AccountRepository
from app.schemas.analytics import NetWorthResponse

METHODOLOGY = (
    "Sum of active account balances; credit cards, loans, and mortgages are "
    "subtracted as liabilities, everything else counts as an asset."
)


def compute(db: Session, user_id: uuid.UUID) -> NetWorthResponse:
    """The one metric this schema can compute with zero transaction history
    (Milestone 1's original scope) -- every other module in this package
    needs transaction data to say anything."""
    accounts = AccountRepository(db).list_for_user(user_id)

    by_account_type: dict[str, Decimal] = {}
    assets_total = Decimal("0")
    liabilities_total = Decimal("0")

    for account in accounts:
        if not account.is_active:
            continue
        balance = Decimal(account.current_balance)
        by_account_type[account.account_type] = (
            by_account_type.get(account.account_type, Decimal("0")) + balance
        )
        if account.account_type in LIABILITY_ACCOUNT_TYPES:
            liabilities_total += balance
        else:
            assets_total += balance

    return NetWorthResponse(
        net_worth=assets_total - liabilities_total,
        assets_total=assets_total,
        liabilities_total=liabilities_total,
        by_account_type=by_account_type,
        methodology=METHODOLOGY,
    )
