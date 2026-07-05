import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.account import Account
from app.models.user import User
from app.schemas.account import AccountCreate, AccountPublic
from app.services.account_service import AccountService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountPublic])
def list_accounts(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Account]:
    service = AccountService(db)
    return service.list_for_user(current_user.id)


@router.post("", response_model=AccountPublic, status_code=201)
def create_account(
    payload: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Account:
    service = AccountService(db)
    return service.create(current_user.id, payload)


@router.get("/{account_id}", response_model=AccountPublic)
def get_account(
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Account:
    service = AccountService(db)
    return service.get_for_user(current_user.id, account_id)
