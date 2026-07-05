import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account


class AccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, account_id: uuid.UUID) -> Account | None:
        return self.db.get(Account, account_id)

    def list_for_user(self, user_id: uuid.UUID) -> list[Account]:
        stmt = select(Account).where(Account.user_id == user_id).order_by(Account.created_at)
        return list(self.db.scalars(stmt))

    def create(self, *, user_id: uuid.UUID, **fields: object) -> Account:
        account = Account(user_id=user_id, **fields)
        self.db.add(account)
        self.db.flush()
        return account
