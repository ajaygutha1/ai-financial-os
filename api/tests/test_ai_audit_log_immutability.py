import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.ai_audit_log_repository import AIAuditLogRepository


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
