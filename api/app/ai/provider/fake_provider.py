from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session

from app.ai.provider.base import AIProvider, RawModelResult, ToolDefinition


class FakeAIProvider(AIProvider):
    """Test double: pops pre-scripted `RawModelResult`s instead of calling
    a real model, but still runs every call through the base class's real
    persistence path (AIAuditLogRepository) -- so tests exercise the actual
    audit/hash-chain logic, not a mocked-away version of it."""

    def __init__(self, db: Session, script: list[RawModelResult]) -> None:
        super().__init__(db)
        self._script: Iterator[RawModelResult] = iter(script)
        self.calls: list[dict[str, Any]] = []

    def _call_model(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],
    ) -> RawModelResult:
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        try:
            return next(self._script)
        except StopIteration as exc:
            raise AssertionError(
                "FakeAIProvider script exhausted -- the agent made more model "
                "calls than the test scripted."
            ) from exc
