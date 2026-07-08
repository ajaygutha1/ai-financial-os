import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.ai_audit_hash import GENESIS_HASH, compute_ai_audit_row_hash


@dataclass
class AIAuditChainVerificationResult:
    rows_checked: int
    first_divergent_id: uuid.UUID | None


def verify_ai_audit_log_chain(db: Session) -> AIAuditChainVerificationResult:
    """Same operational verification tool as core.audit_verify, for the
    AI-specific hash chain -- walks ai_audit_log in chain order and
    recomputes each row's hash, flagging the first row that doesn't match."""
    rows = db.execute(
        text(
            "SELECT id, agent_run_id, model, response, tool_calls, created_at, "
            "prev_hash, row_hash FROM ai_audit_log ORDER BY created_at, id"
        )
    ).fetchall()

    expected_prev_hash = GENESIS_HASH
    for checked, row in enumerate(rows):
        if row.prev_hash != expected_prev_hash:
            return AIAuditChainVerificationResult(rows_checked=checked, first_divergent_id=row.id)

        recomputed = compute_ai_audit_row_hash(
            prev_hash=row.prev_hash,
            agent_run_id=row.agent_run_id,
            model=row.model,
            response=row.response,
            tool_calls=row.tool_calls,
            created_at=row.created_at,
        )
        if recomputed != row.row_hash:
            return AIAuditChainVerificationResult(rows_checked=checked, first_divergent_id=row.id)

        expected_prev_hash = row.row_hash

    return AIAuditChainVerificationResult(rows_checked=len(rows), first_divergent_id=None)
