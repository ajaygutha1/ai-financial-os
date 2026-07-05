import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.audit_log = AuditLogRepository(db)

    def register(self, *, email: str, password: str, full_name: str | None) -> User:
        if self.users.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists.")

        user = self.users.create(
            email=email, hashed_password=hash_password(password), full_name=full_name
        )
        self.audit_log.record(event_type="user.registered", user_id=user.id)
        self.db.commit()
        return user

    def authenticate(self, *, email: str, password: str) -> User:
        user = self.users.get_by_email(email)
        if user is None or user.hashed_password is None:
            raise UnauthorizedError("Invalid email or password.")
        if not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password.")
        if not user.is_active:
            raise UnauthorizedError("This account has been deactivated.")

        self.audit_log.record(event_type="user.login", user_id=user.id)
        self.db.commit()
        return user

    def handle_oauth_login(
        self, *, provider: str, provider_account_id: str, email: str, full_name: str | None
    ) -> User:
        oauth_account = self.users.get_oauth_account(provider, provider_account_id)
        if oauth_account is not None:
            user = self.users.get_by_id(oauth_account.user_id)
            assert user is not None
            self.audit_log.record(event_type="user.oauth_login", user_id=user.id)
            self.db.commit()
            return user

        user = self.users.get_by_email(email)
        if user is None:
            user = self.users.create(email=email, hashed_password=None, full_name=full_name)
            self.audit_log.record(event_type="user.registered", user_id=user.id)

        self.users.create_oauth_account(
            user_id=user.id, provider=provider, provider_account_id=provider_account_id
        )
        self.audit_log.record(
            event_type="user.oauth_link", user_id=user.id, metadata={"provider": provider}
        )
        self.db.commit()
        return user

    @staticmethod
    def issue_tokens(user_id: uuid.UUID) -> tuple[str, str]:
        return create_access_token(user_id), create_refresh_token(user_id)
