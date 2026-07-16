import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.budget_target import BudgetTarget
from app.models.category import Category
from app.repositories.budget_target_repository import BudgetTargetRepository
from app.schemas.budget import BudgetTargetPublic, BudgetTargetSet


class BudgetService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.targets = BudgetTargetRepository(db)

    def list_for_user(self, user_id: uuid.UUID) -> list[BudgetTargetPublic]:
        return [self._to_public(t) for t in self.targets.list_for_user(user_id)]

    def set_target(self, user_id: uuid.UUID, payload: BudgetTargetSet) -> BudgetTargetPublic:
        category = self.db.get(Category, payload.category_id)
        if category is None:
            raise ValidationError("category_id does not exist.")

        target = self.targets.upsert(
            user_id=user_id,
            category_id=payload.category_id,
            monthly_target_amount=payload.monthly_target_amount,
        )
        target.category = category
        self.db.commit()
        return self._to_public(target)

    def delete(self, user_id: uuid.UUID, target_id: uuid.UUID) -> None:
        target = self.targets.get_by_id(target_id)
        if target is None or target.user_id != user_id:
            raise NotFoundError("Budget target not found.")
        self.targets.delete(target)
        self.db.commit()

    def _to_public(self, target: BudgetTarget) -> BudgetTargetPublic:
        return BudgetTargetPublic(
            id=target.id,
            category_id=target.category_id,
            category_name=target.category.name,
            monthly_target_amount=target.monthly_target_amount,
            created_at=target.created_at,
        )
