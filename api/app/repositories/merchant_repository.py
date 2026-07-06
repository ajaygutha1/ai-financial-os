import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.merchant import Merchant


class MerchantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _find_by_canonical_name(self, canonical_name: str) -> Merchant | None:
        return self.db.scalar(
            select(Merchant).where(func.lower(Merchant.canonical_name) == canonical_name.lower())
        )

    def find_or_create_by_canonical_name(
        self, canonical_name: str, *, category_id: uuid.UUID | None = None
    ) -> Merchant:
        existing = self._find_by_canonical_name(canonical_name)
        if existing is not None:
            return existing

        # `merchant` is a global table (no user_id scoping) resolved by every
        # concurrently-syncing account/user, so two sessions can both miss on
        # the SELECT above and then both try to INSERT the same canonical
        # name. A SAVEPOINT contains the resulting IntegrityError from
        # ux_merchant_canonical_name_lower to just this insert attempt
        # instead of poisoning the whole transaction, so we can fall back to
        # reading the row the other writer just committed.
        merchant = Merchant(canonical_name=canonical_name, category_id=category_id)
        try:
            with self.db.begin_nested():
                self.db.add(merchant)
                self.db.flush()
        except IntegrityError:
            existing = self._find_by_canonical_name(canonical_name)
            if existing is None:
                raise
            return existing
        return merchant
