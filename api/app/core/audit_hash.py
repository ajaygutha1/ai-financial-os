import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

# Genesis row uses this as its prev_hash so chain verification needs no
# special-case branch for "the first row."
GENESIS_HASH = "0" * 64


def compute_audit_row_hash(
    *,
    prev_hash: str,
    event_type: str,
    user_id: uuid.UUID | None,
    metadata: dict[str, Any] | None,
    created_at: datetime,
) -> str:
    """Deterministic hash linking an audit_log row to its predecessor.

    `created_at` must be supplied by the caller (not left to the column's
    server_default) so the hash can be computed before the row is inserted --
    audit_log's immutability trigger means there is no legitimate way to
    UPDATE a row after the fact to backfill its hash once created_at becomes
    known.

    This algorithm is duplicated (not imported) in migration 0002's backfill
    step, since migrations are frozen historical records that shouldn't
    depend on application code that can change later. Keep the two in sync
    if this function ever changes; a versioned hash algorithm is the fuller
    answer, deferred to Milestone 8's security hardening pass.
    """
    payload = (
        f"{prev_hash}{event_type}{user_id}"
        f"{json.dumps(metadata, sort_keys=True, default=str)}"
        f"{created_at.isoformat()}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
