import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.account import Account, AccountSource
from app.repositories.account_repository import AccountRepository
from app.schemas.account import AccountCreate


class AccountService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounts = AccountRepository(db)

    def list_for_user(self, user_id: uuid.UUID) -> list[Account]:
        return self.accounts.list_for_user(user_id)

    def get_for_user(self, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
        account = self.accounts.get_by_id(account_id)
        if account is None or account.user_id != user_id:
            raise NotFoundError("Account not found.")
        return account

    def create(self, user_id: uuid.UUID, payload: AccountCreate) -> Account:
        account = self.accounts.create(
            user_id=user_id,
            name=payload.name,
            institution_name=payload.institution_name,
            account_type=payload.account_type.value,
            account_subtype=payload.account_subtype,
            currency=payload.currency,
            current_balance=payload.current_balance,
            available_balance=payload.available_balance,
            mask=payload.mask,
            source=AccountSource.MANUAL.value,
        )
        self.db.commit()
        return account
