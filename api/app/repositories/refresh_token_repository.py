import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, update
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_jti(self, jti: str) -> RefreshToken | None:
        return self.db.query(RefreshToken).filter(RefreshToken.jti == jti).one_or_none()

    def create(self, *, user_id: uuid.UUID, jti: str, family_id: uuid.UUID) -> RefreshToken:
        token = RefreshToken(user_id=user_id, jti=jti, family_id=family_id)
        self.db.add(token)
        self.db.flush()
        return token

    def revoke(self, token: RefreshToken) -> None:
        token.revoked_at = datetime.now(UTC)
        self.db.flush()

    def try_revoke(self, token: RefreshToken) -> bool:
        """Atomically revokes the token only if it's still unrevoked,
        returning whether *this* call was the one that revoked it. Unlike
        `revoke` (a plain attribute assignment matched by PK only), the
        conditional `WHERE revoked_at IS NULL` makes read-and-decide a
        single atomic statement: two concurrent callers both presenting the
        same not-yet-revoked token can't both succeed -- only one UPDATE
        matches the WHERE clause, and the loser gets False back and must be
        treated exactly like presenting an already-revoked token."""
        result = cast(
            "CursorResult[Any]",
            self.db.execute(
                update(RefreshToken)
                .where(RefreshToken.id == token.id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC))
            ),
        )
        self.db.flush()
        return result.rowcount > 0

    def revoke_family(self, family_id: uuid.UUID) -> None:
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        self.db.flush()

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        self.db.flush()
