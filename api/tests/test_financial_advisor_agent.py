from typing import Any

import pydantic
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.agents.financial_advisor import AgentIncompleteError, FinancialAdvisorAgent
from app.ai.provider.base import AIRefusalError, RawModelResult, ToolUseCall, UsageInfo
from app.ai.provider.fake_provider import FakeAIProvider
from app.core.ai_audit_verify import verify_ai_audit_log_chain
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.user import User
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.ai_recommendation_repository import AIRecommendationRepository

_USAGE = UsageInfo(input_tokens=100, output_tokens=50, cache_read_tokens=0, cache_creation_tokens=0)


def _tool_call_result(
    name: str, tool_input: dict[str, Any], call_id: str = "toolu_1"
) -> RawModelResult:
    return RawModelResult(
        model="claude-opus-4-8",
        stop_reason="tool_use",
        content=[{"type": "tool_use", "id": call_id, "name": name, "input": tool_input}],
        text=None,
        tool_uses=[ToolUseCall(id=call_id, name=name, input=tool_input)],
        usage=_USAGE,
    )


def _submit_result(recommendation: dict[str, Any], call_id: str = "toolu_2") -> RawModelResult:
    payload = {
        "reasoning_summary": "Checked net worth; balances look stable.",
        "recommendations": [recommendation],
    }
    return _tool_call_result("submit_recommendations", payload, call_id)


def test_agent_happy_path_creates_recommendation_and_audit_trail(
    db_session: Session, test_user: User
) -> None:
    script = [
        _tool_call_result("net_worth", {}),
        _submit_result(
            {
                "title": "You're in good shape",
                "explanation": "Net worth is positive and stable.",
                "category": "general",
                "confidence": 0.8,
                "metrics_used": ["net_worth"],
            }
        ),
    ]
    provider = FakeAIProvider(db_session, script)
    agent = FinancialAdvisorAgent(db_session, provider)

    result = agent.run(user_id=test_user.id, user_message="How am I doing?")

    assert result.recommendations[0].title == "You're in good shape"

    runs = AgentRunRepository(db_session)
    recommendations = AIRecommendationRepository(db_session).list_for_user(test_user.id)
    assert len(recommendations) == 1
    assert recommendations[0].agent_name == "financial_advisor"
    assert recommendations[0].citations["metrics_used"] == ["net_worth"]

    run = runs.get_by_id(recommendations[0].agent_run_id)
    assert run is not None
    assert run.status == AgentRunStatus.COMPLETED

    # Two underlying model calls (one tool call, one submit) -> two audit
    # rows, and the hash chain must verify.
    verification = verify_ai_audit_log_chain(db_session)
    assert verification.rows_checked == 2
    assert verification.first_divergent_id is None


def test_agent_marks_run_failed_when_iterations_exhausted(
    db_session: Session, test_user: User
) -> None:
    # Every call just asks for another tool, never submits -> loop exhausts.
    script = [_tool_call_result("net_worth", {}) for _ in range(10)]
    provider = FakeAIProvider(db_session, script)
    agent = FinancialAdvisorAgent(db_session, provider)

    with pytest.raises(AgentIncompleteError):
        agent.run(user_id=test_user.id, user_message=None)

    recommendations = AIRecommendationRepository(db_session).list_for_user(test_user.id)
    assert recommendations == []


def test_agent_marks_run_failed_on_refusal(db_session: Session, test_user: User) -> None:
    script = [
        RawModelResult(
            model="claude-opus-4-8",
            stop_reason="refusal",
            content=[],
            text=None,
            tool_uses=[],
            usage=_USAGE,
            refusal_category="cyber",
        )
    ]
    provider = FakeAIProvider(db_session, script)
    agent = FinancialAdvisorAgent(db_session, provider)

    with pytest.raises(AIRefusalError):
        agent.run(user_id=test_user.id, user_message=None)

    # The refused call is still audit-logged before the error propagates.
    verification = verify_ai_audit_log_chain(db_session)
    assert verification.rows_checked == 1


def test_out_of_range_confidence_fails_cleanly_without_losing_audit_trail(
    db_session: Session, test_user: User
) -> None:
    # A model-reported confidence outside 0-1 can't be caught by the tool
    # schema (Anthropic schemas can't express min/max), so it must fail at
    # FinancialAdviceResult.model_validate() instead of overflowing the
    # Numeric(3,2) confidence column. Critically, the tool-call audit row
    # from the *first* model turn (net_worth) must still be preserved and
    # the run marked failed, not silently lost.
    script = [
        _tool_call_result("net_worth", {}),
        _submit_result(
            {
                "title": "Overconfident",
                "explanation": "Bogus confidence value from the model.",
                "category": "general",
                "confidence": 15.0,
                "metrics_used": ["net_worth"],
            }
        ),
    ]
    provider = FakeAIProvider(db_session, script)
    agent = FinancialAdvisorAgent(db_session, provider)

    with pytest.raises(pydantic.ValidationError):
        agent.run(user_id=test_user.id, user_message="How am I doing?")

    assert AIRecommendationRepository(db_session).list_for_user(test_user.id) == []

    run = db_session.scalars(
        select(AgentRun).where(AgentRun.user_id == test_user.id)
    ).one()
    assert run.status == AgentRunStatus.FAILED

    # Both model turns (the tool call and the invalid submit attempt) were
    # already audit-logged by generate() before validation failed -- that
    # trail, and the FAILED run status, must be durably committed rather
    # than rolled back with nothing to show for the run.
    verification = verify_ai_audit_log_chain(db_session)
    assert verification.rows_checked == 2
    assert verification.first_divergent_id is None
