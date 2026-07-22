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
        UniqueConstraint("user_id", "provider", name="ux_connector_credential_user_provider"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_item_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Encrypted at rest (Milestone 8) via EncryptedString -- transparent to
    # every caller, which reads/writes plain strings as before.
    access_token_enc: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ConnectorCredentialStatus.ACTIVE.value
    )
