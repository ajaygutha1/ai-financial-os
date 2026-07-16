from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.agents.base import AgentIncompleteError, BaseAgent, BaseRecommendationItem
from app.ai.agents.budget_coach import BudgetCoachAgent
from app.ai.agents.expense_analyst import ExpenseAnalystAgent
from app.ai.agents.financial_advisor import FinancialAdvisorAgent
from app.ai.agents.fraud_detection import FraudDetectionAgent
from app.ai.agents.investment_analyst import InvestmentAnalystAgent
from app.ai.agents.portfolio_risk_analyst import PortfolioRiskAnalystAgent
from app.ai.agents.retirement_planner import RetirementPlannerAgent
from app.ai.agents.tax_advisor import TaxAdvisorAgent
from app.ai.embeddings.base import EmbeddingProvider
from app.ai.embeddings.dependency import get_embedding_provider
from app.ai.provider.base import AIProvider, AIRefusalError
from app.ai.provider.dependency import get_ai_provider
from app.core.config import get_settings
from app.core.db import get_db
from app.core.exceptions import AppError, NotFoundError, ServiceUnavailableError
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.ai_recommendation_repository import AIRecommendationRepository
from app.schemas.ai import (
    AIRecommendationPublic,
    FinancialAdviceRequest,
    FinancialAdviceResponse,
    RecommendationItemPublic,
)

router = APIRouter(prefix="/ai", tags=["ai"])

# URL slug -> agent class. Every agent shares the same request/response
# shape (BaseAgent's run() signature, BaseRecommendationItem's fields), so
# one generic endpoint below serves all of them rather than one hand-written
# endpoint per agent.
AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "financial-advisor": FinancialAdvisorAgent,
    "expense-analyst": ExpenseAnalystAgent,
    "budget-coach": BudgetCoachAgent,
    "retirement-planner": RetirementPlannerAgent,
    "tax-advisor": TaxAdvisorAgent,
    "fraud-detection": FraudDetectionAgent,
    "investment-analyst": InvestmentAnalystAgent,
    "portfolio-risk-analyst": PortfolioRiskAnalystAgent,
}


def _to_response(item: BaseRecommendationItem) -> RecommendationItemPublic:
    return RecommendationItemPublic(
        title=item.title,
        explanation=item.explanation,
        category=item.category,
        confidence=item.confidence,
        metrics_used=item.metrics_used,
        sources_used=item.sources_used,
    )


@router.get("/agents", response_model=list[str])
def list_agents() -> list[str]:
    return sorted(AGENT_REGISTRY)


@router.post("/{agent_slug}/advice", response_model=FinancialAdviceResponse)
def get_agent_advice(
    agent_slug: str,
    payload: FinancialAdviceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
) -> FinancialAdviceResponse:
    agent_cls = AGENT_REGISTRY.get(agent_slug)
    if agent_cls is None:
        raise NotFoundError(f"Unknown agent: {agent_slug!r}.")

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ServiceUnavailableError(
            "AI features aren't configured yet -- set ANTHROPIC_API_KEY on the server."
        )

    agent = agent_cls(db, provider, embeddings)

    try:
        result = agent.run(user_id=current_user.id, user_message=payload.message)
    except AIRefusalError as exc:
        raise AppError(
            f"The AI declined to answer this request (category: {exc.category})."
        ) from exc
    except AgentIncompleteError as exc:
        raise ServiceUnavailableError(str(exc)) from exc

    return FinancialAdviceResponse(
        reasoning_summary=result.reasoning_summary,
        recommendations=[_to_response(item) for item in result.recommendations],
    )


@router.get("/recommendations", response_model=list[AIRecommendationPublic])
def list_recommendations(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[AIRecommendationPublic]:
    repo = AIRecommendationRepository(db)
    recommendations = repo.list_for_user(current_user.id)
    return [AIRecommendationPublic.model_validate(r) for r in recommendations]
