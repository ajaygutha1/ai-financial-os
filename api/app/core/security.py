import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.models.user import User, UserRole

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)

REFRESH_COOKIE_NAME = "finos_refresh_token"

# bcrypt ignores/rejects input past 72 bytes; truncate deliberately rather
# than let long passwords raise at hash time (matches bcrypt's traditional
# behavior, now enforced strictly by the `bcrypt` package itself).
_MAX_PASSWORD_BYTES = 72


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    truncated = plain_password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.checkpw(truncated, hashed_password.encode("utf-8"))


def _create_token(subject: uuid.UUID, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID) -> str:
    return _create_token(
        user_id, TokenType.ACCESS, timedelta(minutes=settings.access_token_ttl_minutes)
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _create_token(
        user_id, TokenType.REFRESH, timedelta(days=settings.refresh_token_ttl_days)
    )


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired token.") from exc

    if payload.get("type") != expected_type.value:
        raise UnauthorizedError("Invalid token type.")
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token.")

    payload = decode_token(credentials.credentials, TokenType.ACCESS)
    user_id = payload.get("sub")

    user = db.get(User, uuid.UUID(user_id)) if user_id else None
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive.")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("This action requires an administrator role.")
    return current_user
