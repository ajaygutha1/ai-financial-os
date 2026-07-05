import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.merchant import Merchant


class MerchantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_or_create_by_canonical_name(
        self, canonical_name: str, *, category_id: uuid.UUID | None = None
    ) -> Merchant:
        existing = self.db.scalar(
            select(Merchant).where(func.lower(Merchant.canonical_name) == canonical_name.lower())
        )
        if existing is not None:
            return existing

        merchant = Merchant(canonical_name=canonical_name, category_id=category_id)
        self.db.add(merchant)
        self.db.flush()
        return merchant
