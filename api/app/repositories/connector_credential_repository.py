import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.connector_credential import ConnectorCredential


class ConnectorCredentialRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, credential_id: uuid.UUID) -> ConnectorCredential | None:
        return self.db.get(ConnectorCredential, credential_id)

    def get_by_user_provider_item(
        self, *, user_id: uuid.UUID, provider: str, external_item_id: str
    ) -> ConnectorCredential | None:
        stmt = select(ConnectorCredential).where(
            ConnectorCredential.user_id == user_id,
            ConnectorCredential.provider == provider,
            ConnectorCredential.external_item_id == external_item_id,
        )
        return self.db.scalar(stmt)

    def get_by_provider_and_item(
        self, *, provider: str, external_item_id: str
    ) -> ConnectorCredential | None:
        """Item ids are globally unique (Plaid-assigned), not user-scoped --
        this is what a webhook payload (no authenticated user in scope) can
        actually key a lookup off of."""
        stmt = select(ConnectorCredential).where(
            ConnectorCredential.provider == provider,
            ConnectorCredential.external_item_id == external_item_id,
        )
        return self.db.scalar(stmt)

    def create(self, *, user_id: uuid.UUID, **fields: object) -> ConnectorCredential:
        credential = ConnectorCredential(user_id=user_id, **fields)
        self.db.add(credential)
        self.db.flush()
        return credential
