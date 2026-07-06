import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.category import Category


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _find_by_name(self, name: str, parent_id: uuid.UUID | None) -> Category | None:
        return self.db.scalar(
            select(Category).where(Category.name == name, Category.parent_id == parent_id)
        )

    def get_or_create(
        self, name: str, *, parent_id: uuid.UUID | None = None, is_system: bool = True
    ) -> Category:
        existing = self._find_by_name(name, parent_id)
        if existing is not None:
            return existing

        # `category` is a global table (no user_id scoping) resolved by
        # every concurrently-syncing account/user, so two sessions can both
        # miss on the SELECT above and then both try to INSERT the same
        # (parent_id, name) pair (or the same top-level name). A SAVEPOINT
        # contains the resulting IntegrityError from ux_category_parent_name
        # / ux_category_top_level_name to just this insert attempt instead
        # of poisoning the whole transaction, so we can fall back to reading
        # the row the other writer just committed.
        category = Category(name=name, parent_id=parent_id, is_system=is_system)
        try:
            with self.db.begin_nested():
                self.db.add(category)
                self.db.flush()
        except IntegrityError:
            existing = self._find_by_name(name, parent_id)
            if existing is None:
                raise
            return existing
        return category
