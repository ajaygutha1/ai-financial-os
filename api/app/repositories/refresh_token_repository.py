import uuid
from datetime import UTC, datetime

from sqlalchemy import update
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
