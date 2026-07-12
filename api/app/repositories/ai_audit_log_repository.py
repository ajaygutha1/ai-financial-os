import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.ai_audit_hash import GENESIS_HASH, compute_ai_audit_row_hash
from app.models.ai_audit_log import AIAuditLog

# Distinct from AuditLogRepository's lock key -- each chain gets its own
# advisory lock so the two audit logs don't unnecessarily serialize against
# each other.
_AI_AUDIT_LOG_CHAIN_LOCK_KEY = 8_942_017_331_204_456


class AIAuditLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        agent_run_id: uuid.UUID,
        user_id: uuid.UUID | None,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tool_calls: list[dict[str, Any]] | None,
        response: dict[str, Any],
        stop_reason: str,
        tokens_input: int,
        tokens_output: int,
        cache_read_tokens: int,
        cache_creation_tokens: int,
        latency_ms: int,
    ) -> AIAuditLog:
        prev_hash = self._latest_row_hash()
        created_at = datetime.now(UTC)
        row_hash = compute_ai_audit_row_hash(
            prev_hash=prev_hash,
            agent_run_id=agent_run_id,
            model=model,
            response=response,
            tool_calls=tool_calls,
            created_at=created_at,
        )
        entry = AIAuditLog(
            agent_run_id=agent_run_id,
            user_id=user_id,
            model=model,
            system_prompt=system_prompt,
            messages=messages,
            tool_calls=tool_calls,
            response=response,
            stop_reason=stop_reason,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
            latency_ms=latency_ms,
            created_at=created_at,
            prev_hash=prev_hash,
            row_hash=row_hash,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_for_agent_run(self, agent_run_id: uuid.UUID) -> list[AIAuditLog]:
        stmt = (
            select(AIAuditLog)
            .where(AIAuditLog.agent_run_id == agent_run_id)
            .order_by(AIAuditLog.created_at)
        )
        return list(self.db.scalars(stmt))

    def _latest_row_hash(self) -> str:
        # `SELECT ... FOR UPDATE ORDER BY ... LIMIT 1` only locks whichever
        # row is currently latest -- it does not stop a second, concurrent
        # transaction from resolving to that same row under READ COMMITTED
        # and computing the same prev_hash, forking the chain (same bug
        # AuditLogRepository had). A transaction-scoped advisory lock on a
        # fixed key instead serializes every record() call globally: the
        # first caller holds the lock until it commits or rolls back, so the
        # next caller blocks here and then genuinely observes the first
        # caller's newly-committed row as latest.
        self.db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _AI_AUDIT_LOG_CHAIN_LOCK_KEY}
        )
        result = self.db.execute(
            text("SELECT row_hash FROM ai_audit_log ORDER BY created_at DESC, id DESC LIMIT 1")
        ).first()
        return result[0] if result else GENESIS_HASH
