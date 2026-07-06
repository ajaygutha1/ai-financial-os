import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, transaction_id: uuid.UUID) -> Transaction | None:
        return self.db.get(Transaction, transaction_id)

    def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        account_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Transaction], int]:
        stmt = select(Transaction).where(Transaction.user_id == user_id)
        count_stmt = (
            select(func.count()).select_from(Transaction).where(Transaction.user_id == user_id)
        )

        if account_id is not None:
            stmt = stmt.where(Transaction.account_id == account_id)
            count_stmt = count_stmt.where(Transaction.account_id == account_id)
        if date_from is not None:
            stmt = stmt.where(Transaction.posted_at >= date_from)
            count_stmt = count_stmt.where(Transaction.posted_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Transaction.posted_at <= date_to)
            count_stmt = count_stmt.where(Transaction.posted_at <= date_to)

        total = self.db.scalar(count_stmt) or 0
        stmt = (
            stmt.order_by(Transaction.posted_at.desc(), Transaction.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self.db.scalars(stmt))
        return items, total

    def find_duplicate_candidates(
        self,
        *,
        account_id: uuid.UUID,
        posted_at: date,
        amount: Decimal,
        merchant_normalized: str | None,
        window_days: int = 2,
    ) -> list[Transaction]:
        stmt = select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.amount == amount,
            Transaction.posted_at.between(
                posted_at - timedelta(days=window_days),
                posted_at + timedelta(days=window_days),
            ),
        )
        if merchant_normalized:
            stmt = stmt.where(Transaction.merchant_normalized == merchant_normalized)
        return list(self.db.scalars(stmt))

    def find_transfer_match(
        self,
        *,
        user_id: uuid.UUID,
        exclude_account_id: uuid.UUID,
        posted_at: date,
        amount: Decimal,
        window_days: int = 2,
    ) -> Transaction | None:
        """A transfer between the user's own accounts shows up as two rows:
        an outflow in one account and an equal-and-opposite inflow in
        another, close together in time. Only matches transactions already
        persisted in a *different* account -- a transfer inherently spans
        two accounts, and a single CSV/OFX import only ever touches one.
        """
        stmt = (
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.account_id != exclude_account_id,
                Transaction.amount == -amount,
                Transaction.posted_at.between(
                    posted_at - timedelta(days=window_days),
                    posted_at + timedelta(days=window_days),
                ),
            )
            .order_by(Transaction.posted_at)
        )
        return self.db.scalar(stmt)

    def find_refund_match(
        self,
        *,
        account_id: uuid.UUID,
        merchant_normalized: str | None,
        posted_at: date,
        amount: Decimal,
        window_days: int = 90,
    ) -> Transaction | None:
        """A refund is an equal-and-opposite inflow from the same merchant,
        in the same account, following an earlier purchase -- given a much
        longer window than duplicate/transfer detection since refunds can
        take weeks to process.
        """
        if merchant_normalized is None:
            return None

        stmt = (
            select(Transaction)
            .where(
                Transaction.account_id == account_id,
                Transaction.merchant_normalized == merchant_normalized,
                Transaction.amount == -amount,
                Transaction.posted_at <= posted_at,
                Transaction.posted_at >= posted_at - timedelta(days=window_days),
            )
            .order_by(Transaction.posted_at.desc())
        )
        return self.db.scalar(stmt)

    def bulk_create(self, transactions: list[Transaction]) -> None:
        self.db.add_all(transactions)
        self.db.flush()

    def list_for_analytics(
        self,
        user_id: uuid.UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Transaction]:
        """Unpaginated fetch for analytics aggregation (app/analytics/), with
        `account` and `category_ref` eager-loaded so callers can branch on
        account type / category without N+1 queries. Callers should always
        pass a bounded date range in practice -- this exists for a personal
        finance app's per-user transaction volumes, not an unbounded ledger
        scan."""
        stmt = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .options(joinedload(Transaction.account), joinedload(Transaction.category_ref))
        )
        if date_from is not None:
            stmt = stmt.where(Transaction.posted_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Transaction.posted_at <= date_to)
        return list(self.db.scalars(stmt).unique())
