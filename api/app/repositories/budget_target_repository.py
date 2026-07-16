import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.budget_target import BudgetTarget


class BudgetTargetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, target_id: uuid.UUID) -> BudgetTarget | None:
        return self.db.get(BudgetTarget, target_id)

    def get_by_category(self, user_id: uuid.UUID, category_id: uuid.UUID) -> BudgetTarget | None:
        stmt = select(BudgetTarget).where(
            BudgetTarget.user_id == user_id, BudgetTarget.category_id == category_id
        )
        return self.db.scalar(stmt)

    def list_for_user(self, user_id: uuid.UUID) -> list[BudgetTarget]:
        stmt = (
            select(BudgetTarget)
            .where(BudgetTarget.user_id == user_id)
            .options(joinedload(BudgetTarget.category))
            .order_by(BudgetTarget.created_at)
        )
        return list(self.db.scalars(stmt).unique())

    def upsert(
        self, *, user_id: uuid.UUID, category_id: uuid.UUID, monthly_target_amount: Decimal
    ) -> BudgetTarget:
        """Setting a budget for a category you've already budgeted just
        overwrites the target -- there's exactly one target per
        (user, category), not a history of them."""
        existing = self.get_by_category(user_id, category_id)
        if existing is not None:
            existing.monthly_target_amount = monthly_target_amount
            self.db.flush()
            return existing

        # ux_budget_targets_user_category means two concurrent upserts for a
        # category with no target yet (e.g. a double-submit) can both miss
        # the SELECT above and race to INSERT. A SAVEPOINT contains the
        # resulting IntegrityError to just this attempt; on conflict, fall
        # back to *updating* the row the other writer just committed to this
        # call's amount, rather than discarding it -- upsert's contract is
        # "set the target to this value," not "create only if missing."
        target = BudgetTarget(
            user_id=user_id, category_id=category_id, monthly_target_amount=monthly_target_amount
        )
        try:
            with self.db.begin_nested():
                self.db.add(target)
                self.db.flush()
        except IntegrityError:
            existing = self.get_by_category(user_id, category_id)
            if existing is None:
                raise
            existing.monthly_target_amount = monthly_target_amount
            self.db.flush()
            return existing
        return target

    def delete(self, target: BudgetTarget) -> None:
        self.db.delete(target)
        self.db.flush()
