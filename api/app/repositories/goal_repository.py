import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal import Goal


class GoalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, goal_id: uuid.UUID) -> Goal | None:
        return self.db.get(Goal, goal_id)

    def list_for_user(self, user_id: uuid.UUID) -> list[Goal]:
        stmt = select(Goal).where(Goal.user_id == user_id).order_by(Goal.created_at)
        return list(self.db.scalars(stmt))

    def create(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        target_amount: Decimal,
        target_date: Any | None,
        linked_account_id: uuid.UUID | None,
        manual_current_amount: Decimal,
    ) -> Goal:
        goal = Goal(
            user_id=user_id,
            name=name,
            target_amount=target_amount,
            target_date=target_date,
            linked_account_id=linked_account_id,
            manual_current_amount=manual_current_amount,
        )
        self.db.add(goal)
        self.db.flush()
        return goal

    def delete(self, goal: Goal) -> None:
        self.db.delete(goal)
        self.db.flush()
