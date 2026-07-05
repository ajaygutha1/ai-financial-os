import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.audit_hash import GENESIS_HASH, compute_audit_row_hash
from app.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        event_type: str,
        user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        prev_hash = self._latest_row_hash()
        created_at = datetime.now(UTC)
        row_hash = compute_audit_row_hash(
            prev_hash=prev_hash,
            event_type=event_type,
            user_id=user_id,
            metadata=metadata,
            created_at=created_at,
        )
        entry = AuditLog(
            event_type=event_type,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            event_metadata=metadata,
            ip_address=ip_address,
            created_at=created_at,
            prev_hash=prev_hash,
            row_hash=row_hash,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def _latest_row_hash(self) -> str:
        # FOR UPDATE serializes concurrent record() calls against the same
        # session's transaction so two writers can't both read the same
        # "latest" row and fork the chain.
        result = self.db.execute(
            text(
                "SELECT row_hash FROM audit_log "
                "ORDER BY created_at DESC, id DESC LIMIT 1 FOR UPDATE"
            )
        ).first()
        return result[0] if result else GENESIS_HASH
