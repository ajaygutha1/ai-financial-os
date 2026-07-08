import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_recommendation import AIRecommendation, RecommendationStatus


class AIRecommendationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        agent_run_id: uuid.UUID,
        user_id: uuid.UUID,
        agent_name: str,
        title: str,
        explanation: str,
        category: str | None,
        confidence: Decimal,
        citations: dict[str, Any],
        prompt_version: str,
        model: str,
    ) -> AIRecommendation:
        recommendation = AIRecommendation(
            agent_run_id=agent_run_id,
            user_id=user_id,
            agent_name=agent_name,
            title=title,
            explanation=explanation,
            category=category,
            confidence=confidence,
            citations=citations,
            status=RecommendationStatus.ACTIVE,
            prompt_version=prompt_version,
            model=model,
        )
        self.db.add(recommendation)
        self.db.flush()
        return recommendation

    def list_for_user(
        self, user_id: uuid.UUID, *, status: str = RecommendationStatus.ACTIVE
    ) -> list[AIRecommendation]:
        stmt = (
            select(AIRecommendation)
            .where(AIRecommendation.user_id == user_id, AIRecommendation.status == status)
            .order_by(AIRecommendation.created_at.desc())
        )
        return list(self.db.scalars(stmt))
