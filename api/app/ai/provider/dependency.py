from fastapi import Depends
from sqlalchemy.orm import Session

from app.ai.provider.anthropic_provider import AnthropicProvider
from app.ai.provider.base import AIProvider
from app.core.db import get_db


def get_ai_provider(db: Session = Depends(get_db)) -> AIProvider:
    """FastAPI dependency, overridden in tests with a FakeAIProvider --
    routers depend on this instead of instantiating AnthropicProvider
    directly, so the concrete provider is swappable without touching
    endpoint code."""
    return AnthropicProvider(db)
