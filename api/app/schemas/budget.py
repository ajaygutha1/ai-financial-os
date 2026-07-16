import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CategoryPublic(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class BudgetTargetSet(BaseModel):
    category_id: uuid.UUID
    monthly_target_amount: Decimal = Field(gt=0)


class BudgetTargetPublic(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    monthly_target_amount: Decimal
    created_at: datetime
