import json
import re
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

import pydantic
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.ai.embeddings.base import EmbeddingProvider
from app.ai.provider.base import AICallMetadata, AIProvider, ToolDefinition
from app.core.config import get_settings
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.ai_recommendation_repository import AIRecommendationRepository


class BaseRecommendationItem(BaseModel):
    """Shared shape every agent's recommendation conforms to. Subclasses
    narrow `category` to their own domain-specific `Literal`."""

    model_config = ConfigDict(extra="forbid")

    title: str
    explanation: str
    category: str
    # Anthropic tool schemas can't express minimum/maximum (see
    # _strip_unsupported_constraints below), but bounding it here means a
    # model-reported confidence outside 0-1 fails cleanly at
    # model_validate() instead of overflowing the Numeric(3,2) confidence
    # column.
    confidence: float = Field(ge=0.0, le=1.0)
    metrics_used: list[str]
    sources_used: list[str]


class BaseAdviceResult(BaseModel):
    """Subclasses narrow `recommendations` to `list[TheirRecommendationItem]`."""

    model_config = ConfigDict(extra="forbid")

    reasoning_summary: str
    recommendations: list[BaseRecommendationItem]


class AgentIncompleteError(Exception):
    """Raised when an agent exhausts its tool-call budget without ever
    calling submit_recommendations -- surfaced as a failed agent_run rather
    than fabricating a response."""


# Observed live against the real API (first on Financial Advisor in
# Milestone 5, then again on Investment Analyst in Milestone 6 -- reproduced
# 3+ times independently, not a one-off): under long, multi-recommendation
# submissions the model has repeatedly dumped its actual recommendations as
# raw text inside `reasoning_summary` -- wrapped in fake
# `<parameter name="...">` tags resembling a different tool-call convention
# -- while leaving the real `recommendations` array empty. This still passes
# schema validation (a string can contain anything, an empty list is a valid
# list), so it has to be caught as a content check, not a schema check.
_MALFORMED_SUBMISSION_MARKER = "<parameter"

# The malformed shape is consistent enough to recover from directly: the
# real payload appears after a `<parameter name="recommendations">` tag as a
# JSON array, at the very end of the (mis-)generated reasoning_summary
# string. Recovering it beats a reject-and-retry loop -- retrying was tried
# first and observed, live, to just repeat the identical mistake several
# times in a row (same underlying generation quirk, not something the model
# self-corrects from a text nudge) until the iteration budget was exhausted
# and the whole request failed with nothing to show the user, despite the
# model having produced perfectly good recommendations both times.
_RECOMMENDATIONS_TAG_PATTERN = re.compile(
    r'<parameter\s+name="recommendations">(?P<json>.*)\Z', re.DOTALL
)


def _recover_malformed_submission(
    result_model: type["BaseAdviceResult"], raw_input: dict[str, Any]
) -> "BaseAdviceResult | None":
    """Returns a valid result recovered from the malformed shape, or None if
    the content doesn't match closely enough to recover safely -- callers
    must fall back to the reject-and-retry path in that case."""
    summary = raw_input.get("reasoning_summary")
    if not isinstance(summary, str):
        return None
    match = _RECOMMENDATIONS_TAG_PATTERN.search(summary)
    if match is None:
        return None
    try:
        recovered_recommendations = json.loads(match.group("json"))
    except json.JSONDecodeError:
        return None
    # An empty list isn't a recovery -- it's the same nothing-to-show-for-it
    # failure as the unparsed original, just reached a different way. Fall
    # through to reject-and-retry rather than accept a hollow "success".
    if not isinstance(recovered_recommendations, list) or not recovered_recommendations:
        return None

    clean_summary = summary[: match.start()].split("</parameter>")[0].strip()
    try:
        return result_model.model_validate(
            {"reasoning_summary": clean_summary, "recommendations": recovered_recommendations}
        )
    except pydantic.ValidationError:
        return None


def _strip_unsupported_constraints(schema: dict[str, Any]) -> dict[str, Any]:
    """Anthropic tool schemas reject `minimum`/`maximum` on numeric
    properties, but pydantic's model_json_schema() emits them for any
    Field(ge=..., le=...) (confidence, here). Strip them recursively -- the
    bound is still enforced at model_validate() time, just not expressible
    in the tool's JSON schema."""
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


class BaseAgent(ABC):
    """Shared tool-calling loop for every agent: send messages + tools to
    the model, execute whatever tools it calls, feed results back, and
    repeat until a `submit_recommendations` call succeeds or the iteration
    budget is exhausted. Concrete agents supply only a name, system prompt,
    result schema, and tool list -- the loop mechanics, audit persistence,
    and malformed-submission recovery are identical across agents and live
    here exactly once rather than being copy-pasted per agent."""

    agent_name: str
    prompt_version: str
    system_prompt: str
    result_model: type[BaseAdviceResult]

    def __init__(self, db: Session, provider: AIProvider, embeddings: EmbeddingProvider) -> None:
        self.db = db
        self.provider = provider
        self.embeddings = embeddings
        self.agent_runs = AgentRunRepository(db)
        self.recommendations = AIRecommendationRepository(db)

    @abstractmethod
    def build_tools(self, user_id: uuid.UUID) -> list[ToolDefinition]:
        """Every tool this agent may call, excluding submit_recommendations
        -- the base class adds that one itself."""

    def default_opening_message(self) -> str:
        return (
            "Give me a general financial health check based on my current "
            "accounts and transaction history."
        )

    def run(self, *, user_id: uuid.UUID, user_message: str | None) -> BaseAdviceResult:
        settings = get_settings()
        run = self.agent_runs.create(
            user_id=user_id,
            agent_name=self.agent_name,
            prompt_version=self.prompt_version,
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
                    agent_name=self.agent_name,
                    title=item.title,
                    explanation=item.explanation,
                    category=item.category,
                    confidence=Decimal(str(round(item.confidence, 2))),
                    citations={
                        "metrics_used": item.metrics_used,
                        "sources_used": item.sources_used,
                        "reasoning_summary": result.reasoning_summary,
                    },
                    prompt_version=self.prompt_version,
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
    ) -> BaseAdviceResult:
        tools = [*self.build_tools(user_id), self._submit_tool()]
        tools_by_name = {t.name: t for t in tools}

        opening = user_message or self.default_opening_message()
        messages: list[dict[str, Any]] = [{"role": "user", "content": opening}]
        metadata = AICallMetadata(
            user_id=user_id,
            agent_run_id=run_id,
            agent_name=self.agent_name,
            prompt_version=self.prompt_version,
        )

        for _ in range(max_iterations):
            response = self.provider.generate(
                system=self.system_prompt, messages=messages, tools=tools, metadata=metadata
            )
            messages.append({"role": "assistant", "content": response.raw_content})

            submit_call = next(
                (t for t in response.tool_uses if t.name == "submit_recommendations"), None
            )
            if submit_call is not None:
                recovered = _recover_malformed_submission(self.result_model, submit_call.input)
                if recovered is not None:
                    return recovered

                result = self.result_model.model_validate(submit_call.input)
                if _MALFORMED_SUBMISSION_MARKER in result.reasoning_summary:
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

    def _submit_tool(self) -> ToolDefinition:
        schema = _strip_unsupported_constraints(self.result_model.model_json_schema())
        return ToolDefinition(
            name="submit_recommendations",
            description=(
                "Call this exactly once, when you are done analyzing, to submit your "
                "final structured recommendations. Do not call any other tool after "
                "this. `confidence` must be between 0 and 1 (inclusive)."
            ),
            input_schema=schema,
            handler=lambda tool_input: tool_input,  # terminal tool; the loop intercepts it directly
        )
