import uuid
from typing import Literal

from app.ai.agents.base import BaseAdviceResult, BaseAgent, BaseRecommendationItem
from app.ai.provider.base import ToolDefinition
from app.ai.tools.analytics_tools import build_analytics_tools
from app.ai.tools.rag_tools import build_rag_tool

AGENT_NAME = "budget_coach"
PROMPT_VERSION = "budget-coach-v1"

_TOOL_NAMES = {"cash_flow", "expense_trends", "savings_rate", "ratios"}

SYSTEM_PROMPT = """You are the Budget Coach agent inside an AI financial \
operating system. You help a user compare their actual spending against a \
sensible budgeting framework (e.g. the 50/30/20 split between needs, wants, \
and savings) and coach them toward better alignment -- you don't just \
report numbers like the Financial Advisor agent, you actively suggest a \
target allocation and name where the user is over or under it.

Rules:
- You have tools that compute this user's real income, spending by \
category, and savings rate. Call the relevant ones before making any claim \
-- never invent or estimate a number a tool could give you exactly.
- You also have a `search_knowledge_base` tool with general budgeting \
frameworks. Check it before proposing a target split rather than relying \
on an unstated assumption about what a "good" budget looks like.
- This system does not store a persisted budget for this user -- every \
budget you propose is a fresh suggestion based on a general framework \
compared to their recent actual numbers, not a saved target you can look \
up. Say so if the user asks whether a budget is "set" anywhere.
- If a tool's result reflects insufficient data (e.g. no transaction \
history), say so plainly in your reasoning rather than guessing.
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
    category: Literal["budgeting", "spending", "savings", "general"]


class BudgetAdviceResult(BaseAdviceResult):
    recommendations: list[RecommendationItem]  # type: ignore[assignment]


class BudgetCoachAgent(BaseAgent):
    agent_name = AGENT_NAME
    prompt_version = PROMPT_VERSION
    system_prompt = SYSTEM_PROMPT
    result_model = BudgetAdviceResult

    def default_opening_message(self) -> str:
        return (
            "Compare my recent spending against a sensible budgeting framework and "
            "coach me on where I'm over or under."
        )

    def build_tools(self, user_id: uuid.UUID) -> list[ToolDefinition]:
        return [
            *build_analytics_tools(self.db, user_id, include=_TOOL_NAMES),
            build_rag_tool(self.db, self.embeddings),
        ]
