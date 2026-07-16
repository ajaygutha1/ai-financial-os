import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class FinancialAdviceRequest(BaseModel):
    message: str | None = None


class RecommendationItemPublic(BaseModel):
    title: str
    explanation: str
    category: str
    confidence: float
    metrics_used: list[str]
    sources_used: list[str]


class FinancialAdviceResponse(BaseModel):
    reasoning_summary: str
    recommendations: list[RecommendationItemPublic]


class AIRecommendationPublic(BaseModel):
    id: uuid.UUID
    agent_name: str
    title: str
    explanation: str
    category: str | None
    confidence: Decimal
    citations: dict[str, Any]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
