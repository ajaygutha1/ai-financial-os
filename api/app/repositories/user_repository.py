import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import OAuthAccount, User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def create(self, *, email: str, hashed_password: str | None, full_name: str | None) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            is_verified=hashed_password is None,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def get_oauth_account(self, provider: str, provider_account_id: str) -> OAuthAccount | None:
        return self.db.scalar(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_account_id == provider_account_id,
            )
        )

    def create_oauth_account(
        self, *, user_id: uuid.UUID, provider: str, provider_account_id: str
    ) -> OAuthAccount:
        oauth_account = OAuthAccount(
            user_id=user_id, provider=provider, provider_account_id=provider_account_id
        )
        self.db.add(oauth_account)
        self.db.flush()
        return oauth_account
