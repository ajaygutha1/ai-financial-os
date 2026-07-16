import uuid
from typing import Literal

from app.ai.agents.base import BaseAdviceResult, BaseAgent, BaseRecommendationItem
from app.ai.provider.base import ToolDefinition
from app.ai.tools.analytics_tools import build_analytics_tools
from app.ai.tools.rag_tools import build_rag_tool

AGENT_NAME = "retirement_planner"
PROMPT_VERSION = "retirement-planner-v1"

_TOOL_NAMES = {"net_worth", "retirement_contributions"}

SYSTEM_PROMPT = """You are the Retirement Planner agent inside an AI \
financial operating system. You help a user understand their retirement \
account balances and contribution pace, and give general guidance on \
retirement account tradeoffs.

Rules:
- You have tools that compute this user's real retirement-account balance \
and average monthly contribution. Call the relevant ones before making any \
claim -- never invent or estimate a number a tool could give you exactly.
- You also have a `search_knowledge_base` tool with general retirement- \
account guidance (traditional vs. Roth, contribution tradeoffs). Use it \
before asserting a general principle rather than relying on an unstated \
assumption.
- This system does not know the user's age, target retirement age, or risk \
tolerance -- nothing in this schema captures them. If the user's message \
states any of these, use them; if a recommendation would benefit from one \
you don't have, say so plainly and ask for it rather than assuming a \
default. Never fabricate a projected retirement date or balance from an \
assumed age.
- If a tool's result reflects insufficient data (e.g. no retirement \
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
    category: Literal["retirement", "savings", "general"]


class RetirementAdviceResult(BaseAdviceResult):
    recommendations: list[RecommendationItem]  # type: ignore[assignment]


class RetirementPlannerAgent(BaseAgent):
    agent_name = AGENT_NAME
    prompt_version = PROMPT_VERSION
    system_prompt = SYSTEM_PROMPT
    result_model = RetirementAdviceResult

    def default_opening_message(self) -> str:
        return "Give me a check-up on my retirement account balances and contribution pace."

    def build_tools(self, user_id: uuid.UUID) -> list[ToolDefinition]:
        return [
            *build_analytics_tools(self.db, user_id, include=_TOOL_NAMES),
            build_rag_tool(self.db, self.embeddings),
        ]
