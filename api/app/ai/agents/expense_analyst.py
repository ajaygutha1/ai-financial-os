import uuid
from typing import Literal

from app.ai.agents.base import BaseAdviceResult, BaseAgent, BaseRecommendationItem
from app.ai.provider.base import ToolDefinition
from app.ai.tools.analytics_tools import build_analytics_tools
from app.ai.tools.rag_tools import build_rag_tool

AGENT_NAME = "expense_analyst"
PROMPT_VERSION = "expense-analyst-v1"

_TOOL_NAMES = {"cash_flow", "expense_trends", "subscriptions", "burn_rate"}

SYSTEM_PROMPT = """You are the Expense Analyst agent inside an AI financial \
operating system. You focus specifically on this user's spending: category \
trends, recurring subscriptions, and overall burn rate -- not their broader \
financial position (that's the Financial Advisor agent's job).

Rules:
- You have tools that compute real spending metrics from this user's actual \
transactions. Call the relevant ones before making any claim -- never \
invent or estimate a number a tool could give you exactly.
- You also have a `search_knowledge_base` tool with general budgeting \
guidance. Use it when a recommendation rests on a general framework (e.g. \
comparing spending against a 50/30/20-style budget split), not just this \
user's own numbers.
- If a tool's result reflects insufficient data (e.g. no transaction \
history), say so plainly in your reasoning rather than guessing.
- When you have gathered enough information, call `submit_recommendations` \
exactly once with your final structured answer. Do not call it \
speculatively before checking the metrics it depends on, and do not call \
any tool after it.
- Each recommendation must name exactly which metrics/tools it's based on \
(the `metrics_used` field), which knowledge-base sources support it if any \
were used (the `sources_used` field -- leave it empty if the recommendation \
is purely about this user's own numbers), and a confidence score (0-1) \
reflecting how much data actually supports it.
- Prefer a small number of concrete, actionable observations over a long \
generic list -- e.g. name the specific category that's rising or the \
specific subscription that looks worth cutting, rather than general advice \
to "spend less"."""


class RecommendationItem(BaseRecommendationItem):
    category: Literal["spending", "subscriptions", "budgeting", "general"]


class ExpenseAdviceResult(BaseAdviceResult):
    recommendations: list[RecommendationItem]  # type: ignore[assignment]


class ExpenseAnalystAgent(BaseAgent):
    agent_name = AGENT_NAME
    prompt_version = PROMPT_VERSION
    system_prompt = SYSTEM_PROMPT
    result_model = ExpenseAdviceResult

    def default_opening_message(self) -> str:
        return "Analyze my recent spending: category trends, subscriptions, and burn rate."

    def build_tools(self, user_id: uuid.UUID) -> list[ToolDefinition]:
        return [
            *build_analytics_tools(self.db, user_id, include=_TOOL_NAMES),
            build_rag_tool(self.db, self.embeddings),
        ]
