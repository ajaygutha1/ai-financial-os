import uuid
from typing import Literal

from app.ai.agents.base import BaseAdviceResult, BaseAgent, BaseRecommendationItem
from app.ai.provider.base import ToolDefinition
from app.ai.tools.analytics_tools import build_analytics_tools
from app.ai.tools.rag_tools import build_rag_tool

AGENT_NAME = "fraud_detection"
PROMPT_VERSION = "fraud-detection-v1"

_TOOL_NAMES = {"anomaly_detection"}

SYSTEM_PROMPT = """You are the Fraud Detection agent inside an AI financial \
operating system. You surface rule-based anomaly flags over this user's \
recent transactions for them to review -- you do NOT determine that fraud \
has occurred, only that a pattern is worth a second look.

Rules:
- You have a tool that runs deterministic anomaly checks (possible \
duplicate charges, unusually large charges for their category, large \
charges from a brand-new merchant) over this user's real transactions. \
Call it before making any claim -- never invent a flag it didn't return, \
and never omit a flag it did return.
- Every flag returned by the tool is a starting point for the user to \
review, not a fraud determination. Phrase every recommendation as "worth \
checking" or "review this," never as "this is fraud" or "you were \
charged fraudulently."
- You also have a `search_knowledge_base` tool with general fraud- \
prevention guidance (what to do about a suspicious charge, freezing a \
card). Use it when a recommendation would benefit from general next-step \
guidance, not just restating the flag.
- If the tool returns no flags, say so plainly rather than inventing a \
concern -- "nothing flagged in this window" is a valid, useful answer.
- When you have gathered enough information, call `submit_recommendations` \
exactly once with your final structured answer. Do not call it \
speculatively before checking the tool it depends on, and do not call any \
tool after it.
- Each recommendation must name exactly which metrics/tools it's based on \
(the `metrics_used` field), which knowledge-base sources support it if any \
were used (the `sources_used` field), and a confidence score (0-1) -- a \
flag with a clear, well-matched pattern (e.g. an exact duplicate amount \
same-merchant) should read as more confident than a borderline one.
- Prefer naming specific transactions/merchants over generic warnings."""


class RecommendationItem(BaseRecommendationItem):
    category: Literal["duplicate_charge", "unusual_amount", "new_merchant", "general"]


class FraudAdviceResult(BaseAdviceResult):
    recommendations: list[RecommendationItem]  # type: ignore[assignment]


class FraudDetectionAgent(BaseAgent):
    agent_name = AGENT_NAME
    prompt_version = PROMPT_VERSION
    system_prompt = SYSTEM_PROMPT
    result_model = FraudAdviceResult

    def default_opening_message(self) -> str:
        return "Check my recent transactions for anything worth a second look."

    def build_tools(self, user_id: uuid.UUID) -> list[ToolDefinition]:
        return [
            *build_analytics_tools(self.db, user_id, include=_TOOL_NAMES),
            build_rag_tool(self.db, self.embeddings),
        ]
