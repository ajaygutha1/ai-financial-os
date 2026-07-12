import json
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.ai.provider.base import AICallMetadata, AIProvider, ToolDefinition
from app.ai.tools.analytics_tools import build_analytics_tools
from app.core.config import get_settings
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.ai_recommendation_repository import AIRecommendationRepository

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
- If a tool's result reflects insufficient data (e.g. no transaction \
history, a null value), say so plainly in your reasoning rather than \
guessing what the number might be.
- When you have gathered enough information, call `submit_recommendations` \
exactly once with your final structured answer. Do not call it \
speculatively before checking the metrics it depends on, and do not call \
any tool after it.
- Each recommendation must name exactly which metrics/tools it's based on \
(the `metrics_used` field), and a confidence score (0-1) reflecting how \
much data actually supports it -- a recommendation based on six months of \
consistent data should read as more confident than one based on a single \
thin data point.
- Prefer a small number of concrete, actionable recommendations over a long \
generic list."""


class RecommendationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    explanation: str
    category: Literal["emergency_fund", "debt", "savings", "spending", "subscriptions", "general"]
    confidence: float
    metrics_used: list[str]


class FinancialAdviceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning_summary: str
    recommendations: list[RecommendationItem]


class AgentIncompleteError(Exception):
    """Raised when the agent exhausts its tool-call budget without ever
    calling submit_recommendations -- surfaced as a failed agent_run rather
    than fabricating a response."""


def _submit_tool() -> ToolDefinition:
    return ToolDefinition(
        name="submit_recommendations",
        description=(
            "Call this exactly once, when you are done analyzing, to submit your "
            "final structured financial advice. Do not call any other tool after this."
        ),
        input_schema=FinancialAdviceResult.model_json_schema(),
        handler=lambda tool_input: tool_input,  # terminal tool; the loop intercepts it directly
    )


class FinancialAdvisorAgent:
    def __init__(self, db: Session, provider: AIProvider) -> None:
        self.db = db
        self.provider = provider
        self.agent_runs = AgentRunRepository(db)
        self.recommendations = AIRecommendationRepository(db)

    def run(self, *, user_id: uuid.UUID, user_message: str | None) -> FinancialAdviceResult:
        settings = get_settings()
        run = self.agent_runs.create(
            user_id=user_id,
            agent_name=AGENT_NAME,
            prompt_version=PROMPT_VERSION,
            user_message=user_message,
        )

        try:
            result = self._run_loop(
                user_id=user_id,
                run_id=run.id,
                user_message=user_message,
                max_iterations=settings.ai_max_tool_iterations,
            )
        except Exception as exc:
            self.agent_runs.mark_failed(run, error_message=str(exc))
            self.db.commit()
            raise

        self.agent_runs.mark_completed(run)
        for item in result.recommendations:
            self.recommendations.create(
                agent_run_id=run.id,
                user_id=user_id,
                agent_name=AGENT_NAME,
                title=item.title,
                explanation=item.explanation,
                category=item.category,
                confidence=Decimal(str(round(item.confidence, 2))),
                citations={
                    "metrics_used": item.metrics_used,
                    "reasoning_summary": result.reasoning_summary,
                },
                prompt_version=PROMPT_VERSION,
                model=settings.ai_model,
            )
        self.db.commit()
        return result

    def _run_loop(
        self,
        *,
        user_id: uuid.UUID,
        run_id: uuid.UUID,
        user_message: str | None,
        max_iterations: int,
    ) -> FinancialAdviceResult:
        tools = [*build_analytics_tools(self.db, user_id), _submit_tool()]
        tools_by_name = {t.name: t for t in tools}

        opening = user_message or (
            "Give me a general financial health check based on my current accounts "
            "and transaction history."
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": opening}]
        metadata = AICallMetadata(
            user_id=user_id,
            agent_run_id=run_id,
            agent_name=AGENT_NAME,
            prompt_version=PROMPT_VERSION,
        )

        for _ in range(max_iterations):
            response = self.provider.generate(
                system=SYSTEM_PROMPT, messages=messages, tools=tools, metadata=metadata
            )
            messages.append({"role": "assistant", "content": response.raw_content})

            submit_call = next(
                (t for t in response.tool_uses if t.name == "submit_recommendations"), None
            )
            if submit_call is not None:
                return FinancialAdviceResult.model_validate(submit_call.input)

            if not response.tool_uses:
                # Model stopped without submitting -- nudge once rather than
                # silently failing, in case it just forgot the required last step.
                messages.append(
                    {
                        "role": "user",
                        "content": "Please call submit_recommendations with your final "
                        "structured answer.",
                    }
                )
                continue

            tool_results = []
            for call in response.tool_uses:
                output = tools_by_name[call.name].handler(call.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": json.dumps(output, default=str),
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        raise AgentIncompleteError(
            f"Exceeded {max_iterations} tool-call iterations without a final recommendation."
        )
