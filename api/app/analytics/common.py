import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.account import AccountType
from app.models.transaction import Transaction
from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository

# Sign-convention note -- the one subtlety every module in this package relies
# on. A transaction's `amount` is signed relative to *its own account's*
# balance, not the user's total wealth: `balance_before + amount ==
# balance_after` holds for every account regardless of type (this is exactly
# what Milestone 2's balance reconciliation engine verifies). That means the
# same positive amount means opposite things on an asset account vs. a
# liability account:
#
# - Asset account (checking/savings): positive = money in (income), negative
#   = money out (an expense).
# - Liability account (credit card/loan/mortgage): positive = a new charge
#   that *increases* what's owed (real spending, recorded the moment it
#   happens), negative = a payment or credit that reduces the balance (debt
#   service, not income).
#
# So for cash-flow purposes, "expense" = outflows from asset accounts, plus
# net new charges on credit cards. Loans/mortgages are excluded from the
# expense side entirely -- there's no "purchase" concept there in this
# schema, only balance-reducing payments, which are debt service already
# reflected in the paying account's outflow (or, if paid from outside this
# system, simply aren't counted as income either).
#
# Every helper here also excludes `is_transfer` rows (money moving between a
# user's own accounts is not economic activity) and rows with
# `is_duplicate_of IS NOT NULL` (flagged duplicates that must never be
# double-counted -- see the CSV/OFX dedup pipeline from Milestones 1/2).

LIQUID_ACCOUNT_TYPES = {AccountType.CHECKING.value, AccountType.SAVINGS.value}
CREDIT_ACCOUNT_TYPES = {AccountType.CREDIT_CARD.value}
CASH_FLOW_ACCOUNT_TYPES = LIQUID_ACCOUNT_TYPES | CREDIT_ACCOUNT_TYPES
LIABILITY_ACCOUNT_TYPES = {
    AccountType.CREDIT_CARD.value,
    AccountType.LOAN.value,
    AccountType.MORTGAGE.value,
}


@dataclass
class MonthlyFlow:
    month: date
    income: Decimal = field(default_factory=lambda: Decimal("0"))
    expenses: Decimal = field(default_factory=lambda: Decimal("0"))
    transaction_count: int = 0

    @property
    def net(self) -> Decimal:
        return self.income - self.expenses


def month_start(value: date) -> date:
    return value.replace(day=1)


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def liquid_assets_total(db: Session, user_id: uuid.UUID) -> Decimal:
    accounts = AccountRepository(db).list_for_user(user_id)
    return sum(
        (
            Decimal(a.current_balance)
            for a in accounts
            if a.is_active and a.account_type in LIQUID_ACCOUNT_TYPES
        ),
        Decimal("0"),
    )


def cash_flow_transactions(
    db: Session,
    user_id: uuid.UUID,
    *,
    date_from: date,
    date_to: date | None = None,
) -> list[Transaction]:
    """Non-duplicate, non-transfer transactions in checking/savings/credit-card
    accounts within the window -- the base set every income/expense
    calculation in this package aggregates over."""
    rows = TransactionRepository(db).list_for_analytics(
        user_id, date_from=date_from, date_to=date_to
    )
    return [
        t
        for t in rows
        if not t.is_transfer
        and t.is_duplicate_of is None
        and t.account.account_type in CASH_FLOW_ACCOUNT_TYPES
    ]


def classify_flow(txn: Transaction) -> tuple[Decimal, Decimal]:
    """Returns (income_contribution, expense_contribution) for one transaction,
    per the sign-convention rules documented at the top of this module."""
    amount = Decimal(txn.amount)
    if txn.account.account_type in LIQUID_ACCOUNT_TYPES:
        if amount > 0:
            return amount, Decimal("0")
        return Decimal("0"), -amount
    # Credit card: net charge activity is the expense. A net-negative month
    # (credits/refunds outweighing new charges) reduces that month's expense
    # total rather than counting as income.
    return Decimal("0"), amount


def monthly_income_and_expenses(
    db: Session,
    user_id: uuid.UUID,
    *,
    months: int,
    as_of: date | None = None,
) -> list[MonthlyFlow]:
    """Trailing `months` of income/expense totals, oldest first, zero-filled
    for months with no qualifying activity. The most recent bucket is the
    current (possibly partial) month."""
    as_of = as_of or date.today()
    period_end = month_start(as_of)
    period_start = add_months(period_end, -(months - 1))
    month_keys = [add_months(period_start, i) for i in range(months)]
    buckets = {key: MonthlyFlow(month=key) for key in month_keys}

    for txn in cash_flow_transactions(db, user_id, date_from=period_start, date_to=as_of):
        bucket = buckets.get(month_start(txn.posted_at))
        if bucket is None:
            continue
        income, expense = classify_flow(txn)
        bucket.income += income
        bucket.expenses += expense
        bucket.transaction_count += 1

    return [buckets[key] for key in month_keys]
