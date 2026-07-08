import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from app.core.audit_hash import GENESIS_HASH

__all__ = ["GENESIS_HASH", "compute_ai_audit_row_hash"]


def compute_ai_audit_row_hash(
    *,
    prev_hash: str,
    agent_run_id: uuid.UUID,
    model: str,
    response: dict[str, Any],
    tool_calls: list[dict[str, Any]] | None,
    created_at: datetime,
) -> str:
    """Deterministic hash linking an ai_audit_log row to its predecessor --
    same tamper-evident chain as app.core.audit_hash, over the fields that
    actually vary per call. The system prompt and full message history are
    static/derivable from prompt_version and not worth hashing every row."""
    payload = (
        f"{prev_hash}{agent_run_id}{model}"
        f"{json.dumps(response, sort_keys=True, default=str)}"
        f"{json.dumps(tool_calls, sort_keys=True, default=str)}"
        f"{created_at.isoformat()}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
