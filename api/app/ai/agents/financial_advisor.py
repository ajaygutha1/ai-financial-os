import json
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.ai.embeddings.base import EmbeddingProvider
from app.ai.provider.base import AICallMetadata, AIProvider, ToolDefinition
from app.ai.tools.analytics_tools import build_analytics_tools
from app.ai.tools.rag_tools import build_rag_tool
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


class RecommendationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    explanation: str
    category: Literal["emergency_fund", "debt", "savings", "spending", "subscriptions", "general"]
    # Anthropic tool schemas can't express minimum/maximum (same limitation as
    # analytics_tools.py's months param) -- bounding it here means a
    # model-reported confidence outside 0-1 fails cleanly at
    # model_validate() instead of overflowing the Numeric(3,2) DB column.
    confidence: float = Field(ge=0.0, le=1.0)
    metrics_used: list[str]
    sources_used: list[str]


class FinancialAdviceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning_summary: str
    recommendations: list[RecommendationItem]


class AgentIncompleteError(Exception):
    """Raised when the agent exhausts its tool-call budget without ever
    calling submit_recommendations -- surfaced as a failed agent_run rather
    than fabricating a response."""


# Observed live against the real API (not a hypothetical): under long,
# multi-recommendation submissions the model has, more than once, dumped its
# actual recommendations as raw text inside `reasoning_summary` -- wrapped in
# fake `<parameter name="...">` tags resembling a different tool-call
# convention -- while leaving the real `recommendations` array empty. This
# still passes schema validation (a string can contain anything, an empty
# list is a valid list), so it has to be caught as a content check, not a
# schema check.
_MALFORMED_SUBMISSION_MARKER = "<parameter"


def _is_malformed_submission(result: FinancialAdviceResult) -> bool:
    return _MALFORMED_SUBMISSION_MARKER in result.reasoning_summary


def _strip_unsupported_constraints(schema: dict[str, Any]) -> dict[str, Any]:
    """Anthropic tool schemas reject `minimum`/`maximum` on numeric
    properties (same limitation as analytics_tools.py's months param), but
    pydantic's model_json_schema() emits them for confidence: float =
    Field(ge=0.0, le=1.0). Strip them recursively -- the 0-1 bound is still
    enforced at FinancialAdviceResult.model_validate() time, just not
    expressible in the tool's JSON schema."""
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key in ("minimum", "maximum"):
            continue
        if isinstance(value, dict):
            result[key] = _strip_unsupported_constraints(value)
        elif isinstance(value, list):
            result[key] = [
                _strip_unsupported_constraints(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def _submit_tool() -> ToolDefinition:
    schema = _strip_unsupported_constraints(FinancialAdviceResult.model_json_schema())
    return ToolDefinition(
        name="submit_recommendations",
        description=(
            "Call this exactly once, when you are done analyzing, to submit your "
            "final structured financial advice. Do not call any other tool after this. "
            "`confidence` must be between 0 and 1 (inclusive)."
        ),
        input_schema=schema,
        handler=lambda tool_input: tool_input,  # terminal tool; the loop intercepts it directly
    )


class FinancialAdvisorAgent:
    def __init__(self, db: Session, provider: AIProvider, embeddings: EmbeddingProvider) -> None:
        self.db = db
        self.provider = provider
        self.embeddings = embeddings
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

        # Persisting recommendations is inside the same try/except as the
        # model loop -- every audit-log row generate() flushed during
        # _run_loop() is only committed once, at the bottom, alongside the
        # final run status. If persistence fails (e.g. a DB constraint) after
        # the loop already succeeded, the except branch below still commits
        # a FAILED run and everything flushed so far, rather than letting an
        # uncaught exception propagate with nothing durably saved -- losing
        # the very audit trail this class exists to guarantee.
        try:
            result = self._run_loop(
                user_id=user_id,
                run_id=run.id,
                user_message=user_message,
                max_iterations=settings.ai_max_tool_iterations,
            )
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
                        "sources_used": item.sources_used,
                        "reasoning_summary": result.reasoning_summary,
                    },
                    prompt_version=PROMPT_VERSION,
                    model=settings.ai_model,
                )
        except Exception as exc:
            self.agent_runs.mark_failed(run, error_message=str(exc))
            self.db.commit()
            raise

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
        tools = [
            *build_analytics_tools(self.db, user_id),
            build_rag_tool(self.db, self.embeddings),
            _submit_tool(),
        ]
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
                result = FinancialAdviceResult.model_validate(submit_call.input)
                if _is_malformed_submission(result):
                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": submit_call.id,
                                    "content": (
                                        "That submission was malformed: `recommendations` "
                                        "was empty and `reasoning_summary` contained raw "
                                        "tool-call syntax instead of prose. Resubmit "
                                        "submit_recommendations with each recommendation as "
                                        "its own object in the `recommendations` array, and "
                                        "keep `reasoning_summary` to a short prose summary."
                                    ),
                                    "is_error": True,
                                }
                            ],
                        }
                    )
                    continue
                return result

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
