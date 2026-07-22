import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole


class AdminUserPublic(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}
