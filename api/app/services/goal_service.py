import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.goal import Goal
from app.repositories.account_repository import AccountRepository
from app.repositories.goal_repository import GoalRepository
from app.schemas.goal import GoalCreate, GoalUpdate


class GoalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.goals = GoalRepository(db)
        self.accounts = AccountRepository(db)

    def list_for_user(self, user_id: uuid.UUID) -> list[Goal]:
        return self.goals.list_for_user(user_id)

    def get_for_user(self, user_id: uuid.UUID, goal_id: uuid.UUID) -> Goal:
        goal = self.goals.get_by_id(goal_id)
        if goal is None or goal.user_id != user_id:
            raise NotFoundError("Goal not found.")
        return goal

    def create(self, user_id: uuid.UUID, payload: GoalCreate) -> Goal:
        if payload.linked_account_id is not None:
            self._validate_linked_account(user_id, payload.linked_account_id)

        goal = self.goals.create(
            user_id=user_id,
            name=payload.name,
            target_amount=payload.target_amount,
            target_date=payload.target_date,
            linked_account_id=payload.linked_account_id,
            manual_current_amount=payload.manual_current_amount,
        )
        self.db.commit()
        return goal

    def update(self, user_id: uuid.UUID, goal_id: uuid.UUID, payload: GoalUpdate) -> Goal:
        goal = self.get_for_user(user_id, goal_id)
        updates = payload.model_dump(exclude_unset=True)

        if "linked_account_id" in updates and updates["linked_account_id"] is not None:
            self._validate_linked_account(user_id, updates["linked_account_id"])

        for field, value in updates.items():
            setattr(goal, field, value)

        self.db.commit()
        return goal

    def delete(self, user_id: uuid.UUID, goal_id: uuid.UUID) -> None:
        goal = self.get_for_user(user_id, goal_id)
        self.goals.delete(goal)
        self.db.commit()

    def _validate_linked_account(self, user_id: uuid.UUID, account_id: uuid.UUID) -> None:
        account = self.accounts.get_by_id(account_id)
        if account is None or account.user_id != user_id:
            raise ValidationError("linked_account_id must reference one of your own accounts.")
