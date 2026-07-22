import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


class AdminService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)

    def list_users(self) -> list[User]:
        return self.users.list_all()

    def get_user(self, user_id: uuid.UUID) -> User:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    def deactivate_user(self, acting_admin: User, user_id: uuid.UUID) -> User:
        if acting_admin.id == user_id:
            raise ValidationError("Admins cannot deactivate their own account.")

        user = self.get_user(user_id)
        user.is_active = False
        # Deactivation should end active sessions immediately rather than
        # waiting out the short access-token TTL -- any refresh attempt is
        # already blocked by get_current_user's is_active check, but this
        # also closes the (small) window on the still-valid access token's
        # remaining lifetime for anything that re-checks the DB.
        self.refresh_tokens.revoke_all_for_user(user_id)
        self.db.commit()
        return user
