import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.account import AccountType
from app.repositories.account_repository import AccountRepository
from app.schemas.analytics import NetWorthResponse

# Account types that reduce net worth (money owed) rather than add to it.
LIABILITY_TYPES = {
    AccountType.CREDIT_CARD.value,
    AccountType.LOAN.value,
    AccountType.MORTGAGE.value,
}


class NetWorthService:
    """Milestone 1's minimal analytics surface — sums current account balances.
    The full modular analytics engine (cash flow, trends, forecasting, etc.)
    is built out in Milestone 3; this establishes the one metric the M1
    dashboard needs without pulling that engine forward prematurely.
    """

    def __init__(self, db: Session) -> None:
        self.accounts = AccountRepository(db)

    def compute(self, user_id: uuid.UUID) -> NetWorthResponse:
        accounts = self.accounts.list_for_user(user_id)

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
            if account.account_type in LIABILITY_TYPES:
                liabilities_total += balance
            else:
                assets_total += balance

        return NetWorthResponse(
            net_worth=assets_total - liabilities_total,
            assets_total=assets_total,
            liabilities_total=liabilities_total,
            by_account_type=by_account_type,
        )
