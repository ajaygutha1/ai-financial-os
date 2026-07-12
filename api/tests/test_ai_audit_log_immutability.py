import threading

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from app.core.ai_audit_verify import verify_ai_audit_log_chain
from app.models.user import User
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.ai_audit_log_repository import (
    _AI_AUDIT_LOG_CHAIN_LOCK_KEY,
    AIAuditLogRepository,
)


def _make_audit_row(db_session: Session, test_user: User):
    run = AgentRunRepository(db_session).create(
        user_id=test_user.id,
        agent_name="financial_advisor",
        prompt_version="test-v1",
        user_message=None,
    )
    entry = AIAuditLogRepository(db_session).record(
        agent_run_id=run.id,
        user_id=test_user.id,
        model="claude-opus-4-8",
        system_prompt="system",
        messages=[{"role": "user", "content": "hi"}],
        tool_calls=None,
        response={"content": [], "stop_reason": "end_turn"},
        stop_reason="end_turn",
        tokens_input=10,
        tokens_output=5,
        cache_read_tokens=0,
        cache_creation_tokens=0,
        latency_ms=100,
    )
    db_session.commit()
    return entry


def test_update_is_rejected(db_session: Session, test_user: User) -> None:
    entry = _make_audit_row(db_session, test_user)

    with pytest.raises(ProgrammingError, match="ai_audit_log rows are immutable"):
        db_session.execute(
            text("UPDATE ai_audit_log SET stop_reason = 'tampered' WHERE id = :id"),
            {"id": entry.id},
        )
    db_session.rollback()


def test_delete_is_rejected(db_session: Session, test_user: User) -> None:
    entry = _make_audit_row(db_session, test_user)

    with pytest.raises(ProgrammingError, match="ai_audit_log rows are immutable"):
        db_session.execute(text("DELETE FROM ai_audit_log WHERE id = :id"), {"id": entry.id})
    db_session.rollback()


def test_truncate_is_rejected(db_session: Session, test_user: User) -> None:
    _make_audit_row(db_session, test_user)

    with pytest.raises(ProgrammingError, match="ai_audit_log rows are immutable"):
        db_session.execute(text("TRUNCATE ai_audit_log"))
    db_session.rollback()


def test_advisory_lock_serializes_concurrent_latest_hash_reads(engine: Engine) -> None:
    # Deterministic proof that _latest_row_hash() genuinely serializes
    # callers via the advisory lock (mirrors
    # test_audit_log_immutability.py's equivalent test for the original
    # audit_log chain) -- not dependent on winning a real timing race against
    # a concurrent INSERT, which is too narrow a window to reproduce reliably.
    lock_acquired = threading.Event()
    release_lock = threading.Event()
    second_lock_acquired = threading.Event()

    def _hold_lock() -> None:
        conn = engine.connect()
        conn.execute(text("BEGIN"))
        conn.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _AI_AUDIT_LOG_CHAIN_LOCK_KEY}
        )
        lock_acquired.set()
        release_lock.wait(timeout=5)
        conn.execute(text("COMMIT"))
        conn.close()

    def _contend_for_lock() -> None:
        conn = engine.connect()
        conn.execute(text("BEGIN"))
        conn.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _AI_AUDIT_LOG_CHAIN_LOCK_KEY}
        )
        second_lock_acquired.set()
        conn.execute(text("COMMIT"))
        conn.close()

    holder = threading.Thread(target=_hold_lock)
    holder.start()
    assert lock_acquired.wait(timeout=5), "first thread never acquired the advisory lock"

    waiter = threading.Thread(target=_contend_for_lock)
    waiter.start()

    assert not second_lock_acquired.wait(timeout=0.3), (
        "a second transaction acquired the advisory lock while the first still held it"
    )

    release_lock.set()
    holder.join(timeout=5)
    waiter.join(timeout=5)
    assert second_lock_acquired.is_set()


def test_concurrent_record_calls_do_not_fork_the_chain(
    db_session: Session, engine: Engine, test_user: User
) -> None:
    run = AgentRunRepository(db_session).create(
        user_id=test_user.id,
        agent_name="financial_advisor",
        prompt_version="test-v1",
        user_message=None,
    )
    db_session.commit()
    run_id = run.id

    session_factory = sessionmaker(bind=engine)
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def _write(stop_reason: str) -> None:
        session = session_factory()
        try:
            barrier.wait(timeout=5)
            AIAuditLogRepository(session).record(
                agent_run_id=run_id,
                user_id=test_user.id,
                model="claude-opus-4-8",
                system_prompt="system",
                messages=[{"role": "user", "content": "hi"}],
                tool_calls=None,
                response={"content": [], "stop_reason": stop_reason},
                stop_reason=stop_reason,
                tokens_input=10,
                tokens_output=5,
                cache_read_tokens=0,
                cache_creation_tokens=0,
                latency_ms=100,
            )
            session.commit()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            session.close()

    threads = [
        threading.Thread(target=_write, args=("end_turn",)),
        threading.Thread(target=_write, args=("tool_use",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"concurrent record() calls raised: {errors}"

    result = verify_ai_audit_log_chain(db_session)
    assert result.first_divergent_id is None, (
        "concurrent record() calls forked the ai_audit_log hash chain"
    )
