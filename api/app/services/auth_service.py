import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.audit_log = AuditLogRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)

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

    def issue_tokens(
        self, user_id: uuid.UUID, *, family_id: uuid.UUID | None = None
    ) -> tuple[str, str]:
        """Issues a fresh access+refresh pair. `family_id` is None for a
        brand-new login (starts a new rotation chain); rotate_refresh_token
        passes the presented token's own family_id to continue the same
        chain instead of starting a new one."""
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)
        jti = decode_token(refresh_token, TokenType.REFRESH)["jti"]
        self.refresh_tokens.create(user_id=user_id, jti=jti, family_id=family_id or uuid.uuid4())
        self.db.commit()
        return access_token, refresh_token

    def rotate_refresh_token(self, presented_token: str) -> tuple[str, str]:
        """Validates and rotates a refresh token -- the presented token is
        revoked and a new one is issued in the same family. Reuse of an
        already-revoked token (one already rotated away by an earlier
        /refresh call) revokes the *entire* family and raises: that pattern
        only happens if the token was copied, since the legitimate client
        always moves forward through the chain, never back to a token it
        already exchanged."""
        payload = decode_token(presented_token, TokenType.REFRESH)
        user_id = uuid.UUID(payload["sub"])
        jti = payload["jti"]

        user = self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("User not found or inactive.")

        token_row = self.refresh_tokens.get_by_jti(jti)
        if token_row is None:
            raise UnauthorizedError("Refresh token not recognized.")
        if token_row.revoked_at is not None:
            self.refresh_tokens.revoke_family(token_row.family_id)
            self.db.commit()
            raise UnauthorizedError(
                "This refresh token was already used -- the session has been revoked."
            )

        self.refresh_tokens.revoke(token_row)
        return self.issue_tokens(user_id, family_id=token_row.family_id)

    def revoke_refresh_token(self, presented_token: str) -> None:
        """True server-side logout: the presented token's entire family is
        revoked, so a copy of it (already in an attacker's hands, or simply
        still sitting in another device's cookie jar) can never be
        exchanged again -- unlike only clearing the client-side cookie."""
        try:
            payload = decode_token(presented_token, TokenType.REFRESH)
        except UnauthorizedError:
            return  # Already invalid/expired -- nothing to revoke.

        token_row = self.refresh_tokens.get_by_jti(payload["jti"])
        if token_row is not None:
            self.refresh_tokens.revoke_family(token_row.family_id)
            self.db.commit()
