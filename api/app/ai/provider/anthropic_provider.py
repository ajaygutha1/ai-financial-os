from typing import Any, cast

import anthropic
from anthropic.types import MessageParam, OutputConfigParam, ThinkingConfigAdaptiveParam, ToolParam
from sqlalchemy.orm import Session

from app.ai.provider.base import (
    AIProvider,
    RawModelResult,
    ToolDefinition,
    ToolUseCall,
    UsageInfo,
)
from app.core.config import get_settings


def _tool_to_anthropic(tool: ToolDefinition) -> ToolParam:
    return cast(
        ToolParam,
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "strict": True,
        },
    )


class AnthropicProvider(AIProvider):
    """The only module that may `import anthropic` -- every agent talks to
    the `AIProvider` interface instead. Sync client, matching the rest of
    this codebase's sync SQLAlchemy/FastAPI style rather than introducing
    async for just this one subsystem."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)
        settings = get_settings()
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.ai_model
        self._max_tokens = settings.ai_max_tokens
        self._effort = settings.ai_effort

    def _call_model(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],
    ) -> RawModelResult:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=cast(list[MessageParam], messages),
            tools=[_tool_to_anthropic(t) for t in tools],
            thinking=cast(
                ThinkingConfigAdaptiveParam, {"type": "adaptive", "display": "summarized"}
            ),
            output_config=cast(OutputConfigParam, {"effort": self._effort}),
        )

        content = [block.model_dump(mode="json") for block in response.content]
        text = next((b.text for b in response.content if b.type == "text"), None)
        tool_uses = [
            ToolUseCall(id=b.id, name=b.name, input=b.input)
            for b in response.content
            if b.type == "tool_use"
        ]
        usage = UsageInfo(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_read_tokens=response.usage.cache_read_input_tokens or 0,
            cache_creation_tokens=response.usage.cache_creation_input_tokens or 0,
        )
        # Non-streaming responses always carry a stop_reason; the SDK types it
        # as optional only because the same Message model backs stream events.
        stop_reason = response.stop_reason or "unknown"
        refusal_category = None
        if stop_reason == "refusal" and response.stop_details is not None:
            refusal_category = response.stop_details.category

        return RawModelResult(
            model=self._model,
            stop_reason=stop_reason,
            content=content,
            text=text,
            tool_uses=tool_uses,
            usage=usage,
            refusal_category=refusal_category,
        )
