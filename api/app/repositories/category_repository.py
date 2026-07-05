import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(
        self, name: str, *, parent_id: uuid.UUID | None = None, is_system: bool = True
    ) -> Category:
        existing = self.db.scalar(
            select(Category).where(Category.name == name, Category.parent_id == parent_id)
        )
        if existing is not None:
            return existing

        category = Category(name=name, parent_id=parent_id, is_system=is_system)
        self.db.add(category)
        self.db.flush()
        return category
