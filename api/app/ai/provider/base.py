import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.ai_audit_log_repository import AIAuditLogRepository


@dataclass
class AICallMetadata:
    user_id: uuid.UUID
    agent_run_id: uuid.UUID
    agent_name: str
    prompt_version: str


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    # Executed by the agent orchestrating the loop, not the provider -- the
    # provider only ever sends name/description/input_schema to the model.
    handler: Callable[[dict[str, Any]], Any]


@dataclass
class ToolUseCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class UsageInfo:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int


@dataclass
class AIResponse:
    stop_reason: str
    text: str | None
    tool_uses: list[ToolUseCall]
    raw_content: list[dict[str, Any]]
    usage: UsageInfo


@dataclass
class RawModelResult:
    """What a concrete provider's `_call_model` produces -- already reduced
    to plain, JSON-serializable data so the base class's persistence logic
    doesn't need to know about any SDK's specific block types."""

    model: str
    stop_reason: str
    content: list[dict[str, Any]]
    text: str | None
    tool_uses: list[ToolUseCall]
    usage: UsageInfo
    refusal_category: str | None = None


class AIRefusalError(Exception):
    """Raised when the model declines a request on safety grounds
    (stop_reason == "refusal"). The call is still audit-logged before this
    is raised -- callers must not silently retry with the same prompt."""

    def __init__(self, category: str | None) -> None:
        self.category = category
        super().__init__(f"AI request refused (category={category!r})")


class AIProvider(ABC):
    """Every agent talks to this interface, never an LLM SDK directly (only
    app/ai/provider/anthropic_provider.py may `import anthropic`) -- swapping
    or adding providers later means writing one new `_call_model`
    implementation. `generate()` itself is concrete: it wraps every
    underlying call with a persisted audit record *before* returning, so
    audit logging is structurally impossible for an agent to bypass."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @abstractmethod
    def _call_model(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],
    ) -> RawModelResult: ...

    def generate(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],
        metadata: AICallMetadata,
    ) -> AIResponse:
        start = time.monotonic()
        raw = self._call_model(system=system, messages=messages, tools=tools)
        latency_ms = int((time.monotonic() - start) * 1000)

        tool_calls = (
            [{"name": t.name, "input": t.input} for t in raw.tool_uses] if raw.tool_uses else None
        )
        AIAuditLogRepository(self.db).record(
            agent_run_id=metadata.agent_run_id,
            user_id=metadata.user_id,
            model=raw.model,
            system_prompt=system,
            messages=messages,
            tool_calls=tool_calls,
            response={"content": raw.content, "stop_reason": raw.stop_reason},
            stop_reason=raw.stop_reason,
            tokens_input=raw.usage.input_tokens,
            tokens_output=raw.usage.output_tokens,
            cache_read_tokens=raw.usage.cache_read_tokens,
            cache_creation_tokens=raw.usage.cache_creation_tokens,
            latency_ms=latency_ms,
        )

        if raw.stop_reason == "refusal":
            raise AIRefusalError(raw.refusal_category)

        return AIResponse(
            stop_reason=raw.stop_reason,
            text=raw.text,
            tool_uses=raw.tool_uses,
            raw_content=raw.content,
            usage=raw.usage,
        )
