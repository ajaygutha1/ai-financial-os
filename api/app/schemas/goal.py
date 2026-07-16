import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    target_amount: Decimal = Field(gt=0)
    target_date: date | None = None
    # Exactly one of these two ways to track progress -- validated in the
    # service layer (a Pydantic model-level check would work too, but the
    # service already owns "does this account belong to this user" and it's
    # clearer to keep both checks in one place).
    linked_account_id: uuid.UUID | None = None
    manual_current_amount: Decimal = Decimal("0")


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    target_amount: Decimal | None = Field(default=None, gt=0)
    target_date: date | None = None
    linked_account_id: uuid.UUID | None = None
    manual_current_amount: Decimal | None = None
    status: str | None = None


class GoalPublic(BaseModel):
    id: uuid.UUID
    name: str
    target_amount: Decimal
    target_date: date | None
    linked_account_id: uuid.UUID | None
    current_amount: Decimal
    progress_pct: Decimal
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
