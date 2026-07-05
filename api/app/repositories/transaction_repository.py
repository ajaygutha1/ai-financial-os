import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

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

    def bulk_create(self, transactions: list[Transaction]) -> None:
        self.db.add_all(transactions)
        self.db.flush()
