import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class TransactionPublic(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    posted_at: date
    amount: Decimal
    currency: str
    merchant_raw: str | None
    merchant_normalized: str | None
    description: str | None
    category: str | None
    transaction_type: str
    is_transfer: bool
    is_duplicate_of: uuid.UUID | None
    import_source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    items: list[TransactionPublic]
    total: int
    page: int
    page_size: int
