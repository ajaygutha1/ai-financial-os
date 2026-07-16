from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.category import Category
from app.models.user import User
from app.schemas.budget import CategoryPublic

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryPublic])
def list_categories(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Category]:
    # Categories are a global (non-user-scoped) taxonomy -- auth is still
    # required since this is only useful to an already-logged-in user
    # picking a category for a budget target, not a public endpoint.
    stmt = select(Category).order_by(Category.name)
    return list(db.scalars(stmt))
