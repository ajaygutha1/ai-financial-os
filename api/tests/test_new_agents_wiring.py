from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.ai.agents.base import BaseAgent
from app.ai.agents.budget_coach import BudgetCoachAgent
from app.ai.agents.expense_analyst import ExpenseAnalystAgent
from app.ai.agents.fraud_detection import FraudDetectionAgent
from app.ai.agents.investment_analyst import InvestmentAnalystAgent
from app.ai.agents.portfolio_risk_analyst import PortfolioRiskAnalystAgent
from app.ai.agents.retirement_planner import RetirementPlannerAgent
from app.ai.agents.tax_advisor import TaxAdvisorAgent
from app.ai.embeddings.fake_provider import FakeEmbeddingProvider
from app.ai.provider.base import RawModelResult, ToolUseCall, UsageInfo
from app.ai.provider.fake_provider import FakeAIProvider
from app.models.user import User
from app.repositories.ai_recommendation_repository import AIRecommendationRepository

_USAGE = UsageInfo(input_tokens=100, output_tokens=50, cache_read_tokens=0, cache_creation_tokens=0)

# (agent class, expected non-terminal tool names, a category valid for that
# agent's own RecommendationItem Literal)
_AGENT_CASES: list[tuple[type[BaseAgent], set[str], str]] = [
    (
        ExpenseAnalystAgent,
        {"cash_flow", "expense_trends", "subscriptions", "burn_rate"},
        "spending",
    ),
    (
        BudgetCoachAgent,
        {"cash_flow", "expense_trends", "savings_rate", "ratios", "budget_vs_actual"},
        "budgeting",
    ),
    (RetirementPlannerAgent, {"net_worth", "retirement_contributions"}, "retirement"),
    (TaxAdvisorAgent, {"taxable_events"}, "general"),
    (FraudDetectionAgent, {"anomaly_detection"}, "general"),
    (InvestmentAnalystAgent, {"net_worth"}, "allocation"),
    (PortfolioRiskAnalystAgent, {"net_worth"}, "concentration"),
]


@pytest.mark.parametrize("agent_cls,expected_tools,_category", _AGENT_CASES)
def test_build_tools_is_scoped_to_the_agents_own_metrics(
    agent_cls: type[BaseAgent],
    expected_tools: set[str],
    _category: str,
    db_session: Session,
    test_user: User,
) -> None:
    agent = agent_cls(db_session, FakeAIProvider(db_session, []), FakeEmbeddingProvider())

    tools = agent.build_tools(test_user.id)

    assert {t.name for t in tools} == {*expected_tools, "search_knowledge_base"}


def _tool_call_result(name: str, tool_input: dict[str, Any], call_id: str) -> RawModelResult:
    return RawModelResult(
        model="claude-opus-4-8",
        stop_reason="tool_use",
        content=[{"type": "tool_use", "id": call_id, "name": name, "input": tool_input}],
        text=None,
        tool_uses=[ToolUseCall(id=call_id, name=name, input=tool_input)],
        usage=_USAGE,
    )


def _submit_result(agent_cls: type[BaseAgent], category: str, call_id: str) -> RawModelResult:
    payload = {
        "reasoning_summary": "Checked the available metrics; here is a concrete recommendation.",
        "recommendations": [
            {
                "title": "A concrete recommendation",
                "explanation": "Based on the data actually available.",
                "category": category,
                "confidence": 0.6,
                "metrics_used": [],
                "sources_used": [],
            }
        ],
    }
    return _tool_call_result("submit_recommendations", payload, call_id)


@pytest.mark.parametrize("agent_cls,_expected_tools,category", _AGENT_CASES)
def test_agent_completes_full_loop_with_its_own_schema(
    agent_cls: type[BaseAgent],
    _expected_tools: set[str],
    category: str,
    db_session: Session,
    test_user: User,
) -> None:
    script = [_submit_result(agent_cls, category, call_id="toolu_1")]
    provider = FakeAIProvider(db_session, script)
    agent = agent_cls(db_session, provider, FakeEmbeddingProvider())

    result = agent.run(user_id=test_user.id, user_message="Give me a check-up.")

    assert len(result.recommendations) == 1
    assert result.recommendations[0].category == category

    recommendations = AIRecommendationRepository(db_session).list_for_user(test_user.id)
    assert len(recommendations) == 1
    assert recommendations[0].agent_name == agent_cls.agent_name
