from typing import Any

import pydantic
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.agents.financial_advisor import AgentIncompleteError, FinancialAdvisorAgent
from app.ai.embeddings.fake_provider import FakeEmbeddingProvider
from app.ai.provider.base import AIRefusalError, RawModelResult, ToolUseCall, UsageInfo
from app.ai.provider.fake_provider import FakeAIProvider
from app.core.ai_audit_verify import verify_ai_audit_log_chain
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.rag_chunk import RAGChunk
from app.models.user import User
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.ai_recommendation_repository import AIRecommendationRepository
from app.repositories.rag_chunk_repository import RAGChunkRepository
from app.repositories.rag_document_repository import RAGDocumentRepository

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
                "sources_used": [],
            }
        ),
    ]
    provider = FakeAIProvider(db_session, script)
    agent = FinancialAdvisorAgent(db_session, provider, FakeEmbeddingProvider())

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
    agent = FinancialAdvisorAgent(db_session, provider, FakeEmbeddingProvider())

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
    agent = FinancialAdvisorAgent(db_session, provider, FakeEmbeddingProvider())

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
                "sources_used": [],
            }
        ),
    ]
    provider = FakeAIProvider(db_session, script)
    agent = FinancialAdvisorAgent(db_session, provider, FakeEmbeddingProvider())

    with pytest.raises(pydantic.ValidationError):
        agent.run(user_id=test_user.id, user_message="How am I doing?")

    assert AIRecommendationRepository(db_session).list_for_user(test_user.id) == []

    run = db_session.scalars(select(AgentRun).where(AgentRun.user_id == test_user.id)).one()
    assert run.status == AgentRunStatus.FAILED

    # Both model turns (the tool call and the invalid submit attempt) were
    # already audit-logged by generate() before validation failed -- that
    # trail, and the FAILED run status, must be durably committed rather
    # than rolled back with nothing to show for the run.
    verification = verify_ai_audit_log_chain(db_session)
    assert verification.rows_checked == 2
    assert verification.first_divergent_id is None


def test_agent_calls_rag_tool_and_records_sources_used(
    db_session: Session, test_user: User
) -> None:
    embeddings = FakeEmbeddingProvider()
    doc_repo = RAGDocumentRepository(db_session)
    document = doc_repo.create(
        title="Emergency Fund Guidelines",
        source="test-fixture",
        category="emergency_fund",
        source_url=None,
        content_hash="emergency-fund-guidelines",
    )
    content = "An emergency fund should cover three to six months of essential expenses."
    RAGChunkRepository(db_session).bulk_create(
        [
            RAGChunk(
                document_id=document.id,
                chunk_index=0,
                content=content,
                embedding=embeddings.embed([content])[0],
                token_count=len(content) // 4,
            )
        ]
    )
    db_session.commit()

    script = [
        _tool_call_result(
            "search_knowledge_base", {"query": "emergency fund target", "category": None}
        ),
        _submit_result(
            {
                "title": "Build up your emergency fund",
                "explanation": "Aim for three to six months of expenses in savings.",
                "category": "emergency_fund",
                "confidence": 0.7,
                "metrics_used": [],
                "sources_used": ["Emergency Fund Guidelines"],
            }
        ),
    ]
    provider = FakeAIProvider(db_session, script)
    agent = FinancialAdvisorAgent(db_session, provider, embeddings)

    result = agent.run(user_id=test_user.id, user_message="How much should I save?")

    assert result.recommendations[0].sources_used == ["Emergency Fund Guidelines"]
    recommendations = AIRecommendationRepository(db_session).list_for_user(test_user.id)
    assert recommendations[0].citations["sources_used"] == ["Emergency Fund Guidelines"]


def test_agent_retries_when_submission_is_malformed(db_session: Session, test_user: User) -> None:
    # Observed live against the real API: the model has dumped its actual
    # recommendations as raw text inside reasoning_summary (wrapped in fake
    # <parameter> tags) while leaving `recommendations` empty -- still
    # schema-valid, so the agent must catch it by content, nudge a retry,
    # and not surface the malformed result to the user.
    malformed = _tool_call_result(
        "submit_recommendations",
        {
            "reasoning_summary": 'garbage</parameter>\n<parameter name="recommendations">[]',
            "recommendations": [],
        },
        call_id="toolu_bad",
    )
    script = [
        malformed,
        _submit_result(
            {
                "title": "You're in good shape",
                "explanation": "Net worth is positive and stable.",
                "category": "general",
                "confidence": 0.8,
                "metrics_used": [],
                "sources_used": [],
            },
            call_id="toolu_good",
        ),
    ]
    provider = FakeAIProvider(db_session, script)
    agent = FinancialAdvisorAgent(db_session, provider, FakeEmbeddingProvider())

    result = agent.run(user_id=test_user.id, user_message="How am I doing?")

    assert len(result.recommendations) == 1
    assert result.recommendations[0].title == "You're in good shape"

    # Both model turns (the malformed attempt and the valid resubmission)
    # are still audit-logged.
    verification = verify_ai_audit_log_chain(db_session)
    assert verification.rows_checked == 2
    assert verification.first_divergent_id is None
