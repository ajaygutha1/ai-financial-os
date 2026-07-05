import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.account import AccountType


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    institution_name: str | None = None
    account_type: AccountType
    account_subtype: str | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    current_balance: Decimal = Decimal("0")
    available_balance: Decimal | None = None
    mask: str | None = Field(default=None, max_length=8)


class AccountPublic(BaseModel):
    id: uuid.UUID
    name: str
    institution_name: str | None
    account_type: str
    account_subtype: str | None
    currency: str
    current_balance: Decimal
    available_balance: Decimal | None
    mask: str | None
    source: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
