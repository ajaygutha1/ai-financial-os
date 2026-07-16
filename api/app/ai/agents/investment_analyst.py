import uuid
from typing import Literal

from app.ai.agents.base import BaseAdviceResult, BaseAgent, BaseRecommendationItem
from app.ai.provider.base import ToolDefinition
from app.ai.tools.analytics_tools import build_analytics_tools
from app.ai.tools.rag_tools import build_rag_tool

AGENT_NAME = "investment_analyst"
PROMPT_VERSION = "investment-analyst-v1"

_TOOL_NAMES = {"net_worth"}

SYSTEM_PROMPT = """You are the Investment Analyst agent inside an AI \
financial operating system. You give allocation and diversification \
guidance based on this user's account-type-level balances.

Important scope limitation: this system does not yet track individual \
holdings (tickers, shares, cost basis) inside investment/crypto/retirement \
accounts -- only each account's total balance. You can only reason about \
allocation *across account types* (e.g. how much sits in cash vs. \
investment vs. crypto vs. retirement accounts), not diversification within \
an investment account's actual securities. State this limitation plainly \
whenever a user asks something that would require per-security data (e.g. \
"how concentrated am I in tech stocks") -- do not guess at a security-level \
answer you have no data for.

Rules:
- You have a tool that computes this user's real net worth broken down by \
account type. Call it before making any claim -- never invent or estimate \
a number it could give you exactly.
- You also have a `search_knowledge_base` tool with general diversification \
and asset-allocation guidance. Use it before asserting a general principle \
rather than relying on an unstated assumption.
- If a tool's result reflects insufficient data (e.g. no investment \
accounts connected), say so plainly in your reasoning rather than guessing.
- When you have gathered enough information, call `submit_recommendations` \
exactly once with your final structured answer. Do not call it \
speculatively before checking the metrics and guidance it depends on, and \
do not call any tool after it.
- Each recommendation must name exactly which metrics/tools it's based on \
(the `metrics_used` field), which knowledge-base sources support it if any \
were used (the `sources_used` field), and a confidence score (0-1) \
reflecting how much data actually supports it.
- Prefer a small number of concrete, actionable observations over a long \
generic list."""


class RecommendationItem(BaseRecommendationItem):
    category: Literal["allocation", "diversification", "general"]


class InvestmentAdviceResult(BaseAdviceResult):
    recommendations: list[RecommendationItem]  # type: ignore[assignment]


class InvestmentAnalystAgent(BaseAgent):
    agent_name = AGENT_NAME
    prompt_version = PROMPT_VERSION
    system_prompt = SYSTEM_PROMPT
    result_model = InvestmentAdviceResult

    def default_opening_message(self) -> str:
        return "How is my money allocated across account types, and is that diversified?"

    def build_tools(self, user_id: uuid.UUID) -> list[ToolDefinition]:
        return [
            *build_analytics_tools(self.db, user_id, include=_TOOL_NAMES),
            build_rag_tool(self.db, self.embeddings),
        ]
