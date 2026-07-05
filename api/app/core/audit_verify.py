import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.audit_hash import GENESIS_HASH, compute_audit_row_hash


@dataclass
class AuditChainVerificationResult:
    rows_checked: int
    first_divergent_id: uuid.UUID | None


def verify_audit_log_chain(db: Session) -> AuditChainVerificationResult:
    """Walks audit_log in chain order and recomputes each row's hash from its
    stored fields, flagging the first row whose stored row_hash doesn't match
    what its content + predecessor imply. An operational/incident-response
    tool, not something called on any request hot path.
    """
    rows = db.execute(
        text(
            "SELECT id, event_type, user_id, metadata, created_at, prev_hash, row_hash "
            "FROM audit_log ORDER BY created_at, id"
        )
    ).fetchall()

    expected_prev_hash = GENESIS_HASH
    for checked, row in enumerate(rows):
        if row.prev_hash != expected_prev_hash:
            return AuditChainVerificationResult(rows_checked=checked, first_divergent_id=row.id)

        recomputed = compute_audit_row_hash(
            prev_hash=row.prev_hash,
            event_type=row.event_type,
            user_id=row.user_id,
            metadata=row.metadata,
            created_at=row.created_at,
        )
        if recomputed != row.row_hash:
            return AuditChainVerificationResult(rows_checked=checked, first_divergent_id=row.id)

        expected_prev_hash = row.row_hash

    return AuditChainVerificationResult(rows_checked=len(rows), first_divergent_id=None)
