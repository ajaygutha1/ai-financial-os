import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.budget import BudgetTargetPublic, BudgetTargetSet
from app.services.budget_service import BudgetService

router = APIRouter(prefix="/budget", tags=["budget"])


@router.get("/targets", response_model=list[BudgetTargetPublic])
def list_budget_targets(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[BudgetTargetPublic]:
    service = BudgetService(db)
    return service.list_for_user(current_user.id)


@router.post("/targets", response_model=BudgetTargetPublic, status_code=201)
def set_budget_target(
    payload: BudgetTargetSet,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetTargetPublic:
    service = BudgetService(db)
    return service.set_target(current_user.id, payload)


@router.delete("/targets/{target_id}", status_code=204)
def delete_budget_target(
    target_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    service = BudgetService(db)
    service.delete(current_user.id, target_id)
