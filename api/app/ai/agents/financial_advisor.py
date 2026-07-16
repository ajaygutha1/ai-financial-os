import uuid
from typing import Literal

from app.ai.agents.base import (
    AgentIncompleteError as AgentIncompleteError,  # re-export
)
from app.ai.agents.base import (
    BaseAdviceResult,
    BaseAgent,
    BaseRecommendationItem,
)
from app.ai.provider.base import ToolDefinition
from app.ai.tools.analytics_tools import build_analytics_tools
from app.ai.tools.rag_tools import build_rag_tool

AGENT_NAME = "financial_advisor"
PROMPT_VERSION = "financial-advisor-v1"

SYSTEM_PROMPT = """You are the Financial Advisor agent inside an AI financial \
operating system. You help a user understand their financial position and \
give concrete, explainable advice.

Rules:
- You have tools that compute real financial metrics from this user's actual \
accounts and transactions. Call the relevant ones before making any claim \
about their finances -- never invent or estimate a number a tool could give \
you exactly.
- You also have a `search_knowledge_base` tool with general financial \
guidance (emergency fund targets, debt payoff strategies, retirement \
account tradeoffs, how tax brackets work, diversification, budgeting \
frameworks). Use it when a recommendation rests on a general principle, not \
just this user's numbers -- e.g. before asserting an emergency-fund target \
or comparing payoff strategies, check what the reference guidance actually \
says rather than relying on your own unstated assumptions.
- If a tool's result reflects insufficient data (e.g. no transaction \
history, a null value), say so plainly in your reasoning rather than \
guessing what the number might be.
- When you have gathered enough information, call `submit_recommendations` \
exactly once with your final structured answer. Do not call it \
speculatively before checking the metrics and guidance it depends on, and \
do not call any tool after it.
- Each recommendation must name exactly which metrics/tools it's based on \
(the `metrics_used` field), which knowledge-base sources support it if any \
were used (the `sources_used` field -- leave it empty if the recommendation \
is purely about this user's own numbers), and a confidence score (0-1) \
reflecting how much data actually supports it -- a recommendation based on \
six months of consistent data should read as more confident than one based \
on a single thin data point.
- Prefer a small number of concrete, actionable recommendations over a long \
generic list."""


class RecommendationItem(BaseRecommendationItem):
    category: Literal["emergency_fund", "debt", "savings", "spending", "subscriptions", "general"]


class FinancialAdviceResult(BaseAdviceResult):
    # Narrowing list[Base] -> list[Subclass] is a supported pydantic pattern
    # (redeclaring a field in a subclass) that mypy's invariant-list check
    # can't see past -- safe here since nothing ever assigns a plain
    # BaseRecommendationItem into this list.
    recommendations: list[RecommendationItem]  # type: ignore[assignment]


class FinancialAdvisorAgent(BaseAgent):
    agent_name = AGENT_NAME
    prompt_version = PROMPT_VERSION
    system_prompt = SYSTEM_PROMPT
    result_model = FinancialAdviceResult

    def build_tools(self, user_id: uuid.UUID) -> list[ToolDefinition]:
        return [
            *build_analytics_tools(self.db, user_id),
            build_rag_tool(self.db, self.embeddings),
        ]
