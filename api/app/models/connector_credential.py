import uuid
from enum import StrEnum

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.encrypted_string import EncryptedString


class ConnectorCredentialStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    ERROR = "error"


class ConnectorCredential(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "connector_credential"
    __table_args__ = (
        # Widened from (user_id, provider) in Milestone 9 -- a user linking
        # a second bank via Plaid is an ordinary case (item_id is Plaid's
        # own per-Item identifier), and the old constraint would have
        # rejected it outright.
        UniqueConstraint(
            "user_id", "provider", "external_item_id", name="ux_connector_credential_user_item"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_item_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Plaid Link's onSuccess metadata includes the institution name directly
    # client-side -- cheaper to pass through at link time than to resolve it
    # server-side via an extra /institutions/get_by_id call.
    institution_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Encrypted at rest (Milestone 8) via EncryptedString -- transparent to
    # every caller, which reads/writes plain strings as before.
    access_token_enc: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ConnectorCredentialStatus.ACTIVE.value
    )
