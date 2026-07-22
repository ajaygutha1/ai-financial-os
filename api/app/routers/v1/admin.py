import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_admin
from app.models.user import User
from app.schemas.admin import AdminUserPublic
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/users", response_model=list[AdminUserPublic])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return AdminService(db).list_users()


@router.get("/users/{user_id}", response_model=AdminUserPublic)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)) -> User:
    return AdminService(db).get_user(user_id)


@router.post("/users/{user_id}/deactivate", response_model=AdminUserPublic)
def deactivate_user(
    user_id: uuid.UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    return AdminService(db).deactivate_user(current_admin, user_id)
