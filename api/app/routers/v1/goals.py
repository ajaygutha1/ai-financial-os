import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.goal import Goal
from app.models.user import User
from app.schemas.goal import GoalCreate, GoalPublic, GoalUpdate
from app.services.goal_service import GoalService

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalPublic])
def list_goals(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Goal]:
    service = GoalService(db)
    return service.list_for_user(current_user.id)


@router.post("", response_model=GoalPublic, status_code=201)
def create_goal(
    payload: GoalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Goal:
    service = GoalService(db)
    return service.create(current_user.id, payload)


@router.get("/{goal_id}", response_model=GoalPublic)
def get_goal(
    goal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Goal:
    service = GoalService(db)
    return service.get_for_user(current_user.id, goal_id)


@router.patch("/{goal_id}", response_model=GoalPublic)
def update_goal(
    goal_id: uuid.UUID,
    payload: GoalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Goal:
    service = GoalService(db)
    return service.update(current_user.id, goal_id, payload)


@router.delete("/{goal_id}", status_code=204)
def delete_goal(
    goal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    service = GoalService(db)
    service.delete(current_user.id, goal_id)
