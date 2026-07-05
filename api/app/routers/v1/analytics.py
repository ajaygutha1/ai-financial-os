from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.analytics import NetWorthResponse
from app.services.net_worth_service import NetWorthService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/net-worth", response_model=NetWorthResponse)
def get_net_worth(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> NetWorthResponse:
    service = NetWorthService(db)
    return service.compute(current_user.id)
