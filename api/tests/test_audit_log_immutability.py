import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.core.audit_verify import verify_audit_log_chain
from app.models.audit_log import AuditLog
from app.repositories.audit_log_repository import AuditLogRepository


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
