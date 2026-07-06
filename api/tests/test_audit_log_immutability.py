import threading
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from app.core.audit_verify import verify_audit_log_chain
from app.models.audit_log import AuditLog
from app.repositories.audit_log_repository import _AUDIT_LOG_CHAIN_LOCK_KEY, AuditLogRepository


def test_update_is_rejected(db_session: Session) -> None:
    repo = AuditLogRepository(db_session)
    entry = repo.record(event_type="test.update_rejected")
    db_session.commit()

    with pytest.raises(ProgrammingError, match="audit_log rows are immutable"):
        db_session.execute(
            text("UPDATE audit_log SET event_type = 'tampered' WHERE id = :id"), {"id": entry.id}
        )
    db_session.rollback()


def test_delete_is_rejected(db_session: Session) -> None:
    repo = AuditLogRepository(db_session)
    entry = repo.record(event_type="test.delete_rejected")
    db_session.commit()

    with pytest.raises(ProgrammingError, match="audit_log rows are immutable"):
        db_session.execute(text("DELETE FROM audit_log WHERE id = :id"), {"id": entry.id})
    db_session.rollback()


def test_truncate_is_rejected(db_session: Session) -> None:
    repo = AuditLogRepository(db_session)
    repo.record(event_type="test.truncate_rejected")
    db_session.commit()

    with pytest.raises(ProgrammingError, match="audit_log rows are immutable"):
        db_session.execute(text("TRUNCATE audit_log"))
    db_session.rollback()


def test_hash_chain_links_sequential_rows(db_session: Session) -> None:
    repo = AuditLogRepository(db_session)
    first = repo.record(event_type="test.chain_first")
    second = repo.record(event_type="test.chain_second")
    db_session.commit()

    assert second.prev_hash == first.row_hash
    assert first.row_hash != second.row_hash


def test_verify_audit_log_chain_detects_tampering(db_session: Session) -> None:
    repo = AuditLogRepository(db_session)
    repo.record(event_type="test.pre_tamper")
    db_session.commit()

    result_before = verify_audit_log_chain(db_session)
    assert result_before.first_divergent_id is None

    # Direct INSERT bypassing the repository, with a deliberately wrong hash --
    # INSERT isn't blocked by the immutability trigger (only UPDATE/DELETE/
    # TRUNCATE are), so this simulates what a bug or a non-conforming write
    # path might produce, for the verification helper to catch.
    tampered_id = uuid.uuid4()
    tampered = AuditLog(
        id=tampered_id,
        event_type="test.tampered",
        prev_hash="0" * 64,
        row_hash="1" * 64,
        created_at=datetime.now(UTC),
    )
    db_session.add(tampered)
    db_session.commit()

    result_after = verify_audit_log_chain(db_session)
    assert result_after.first_divergent_id == tampered_id


def test_advisory_lock_serializes_concurrent_latest_hash_reads(engine: Engine) -> None:
    # `_latest_row_hash()` no longer relies on `SELECT ... FOR UPDATE`
    # (which only locks whichever row is currently latest, and does not
    # stop a second transaction from reading that same row concurrently
    # under READ COMMITTED). Instead it takes a transaction-scoped advisory
    # lock on a fixed key first. This proves the mechanism actually
    # serializes: a second transaction contending for the same key must
    # block until the first commits or rolls back, deterministically --
    # not dependent on winning a real timing race against a genuine
    # concurrent INSERT, which is too narrow a window to reproduce reliably
    # in a test.
    lock_acquired = threading.Event()
    release_lock = threading.Event()
    second_lock_acquired = threading.Event()

    def _hold_lock() -> None:
        conn = engine.connect()
        conn.execute(text("BEGIN"))
        conn.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _AUDIT_LOG_CHAIN_LOCK_KEY}
        )
        lock_acquired.set()
        release_lock.wait(timeout=5)
        conn.execute(text("COMMIT"))
        conn.close()

    def _contend_for_lock() -> None:
        conn = engine.connect()
        conn.execute(text("BEGIN"))
        conn.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _AUDIT_LOG_CHAIN_LOCK_KEY}
        )
        second_lock_acquired.set()
        conn.execute(text("COMMIT"))
        conn.close()

    holder = threading.Thread(target=_hold_lock)
    holder.start()
    assert lock_acquired.wait(timeout=5), "first thread never acquired the advisory lock"

    waiter = threading.Thread(target=_contend_for_lock)
    waiter.start()

    # While the first thread still holds the lock, the second must be blocked.
    assert not second_lock_acquired.wait(timeout=0.3), (
        "a second transaction acquired the advisory lock while the first "
        "still held it -- the lock is not actually serializing callers"
    )

    release_lock.set()
    holder.join(timeout=5)
    waiter.join(timeout=5)
    assert second_lock_acquired.is_set()


def test_concurrent_record_calls_do_not_fork_the_chain(
    db_session: Session, engine: Engine
) -> None:
    # Seed one row on the shared session/connection so both threads below
    # start from the same known prev_hash and the race is exercised on the
    # second append, not the first (genesis) one.
    repo = AuditLogRepository(db_session)
    repo.record(event_type="test.concurrent_seed")
    db_session.commit()

    session_factory = sessionmaker(bind=engine)
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def _write(event_type: str) -> None:
        session = session_factory()
        try:
            barrier.wait(timeout=5)
            AuditLogRepository(session).record(event_type=event_type)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            session.close()

    threads = [
        threading.Thread(target=_write, args=("test.concurrent_a",)),
        threading.Thread(target=_write, args=("test.concurrent_b",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"concurrent record() calls raised: {errors}"

    result = verify_audit_log_chain(db_session)
    assert result.first_divergent_id is None, (
        "concurrent record() calls forked the hash chain -- two rows point at "
        "the same prev_hash instead of forming a single linear chain"
    )
