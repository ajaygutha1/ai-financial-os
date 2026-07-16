from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.embeddings.dependency import get_embedding_provider
from app.ai.embeddings.fake_provider import FakeEmbeddingProvider
from app.ai.provider.base import RawModelResult, ToolUseCall, UsageInfo
from app.ai.provider.dependency import get_ai_provider
from app.ai.provider.fake_provider import FakeAIProvider
from app.main import app as fastapi_app

_USAGE = UsageInfo(input_tokens=100, output_tokens=50, cache_read_tokens=0, cache_creation_tokens=0)


def _submit_only_script() -> list[RawModelResult]:
    payload = {
        "reasoning_summary": "Straightforward check with no transaction history yet.",
        "recommendations": [
            {
                "title": "Connect an account to get started",
                "explanation": "No accounts are linked yet, so there's nothing to analyze.",
                "category": "general",
                "confidence": 0.5,
                "metrics_used": [],
                "sources_used": [],
            }
        ],
    }
    return [
        RawModelResult(
            model="claude-opus-4-8",
            stop_reason="tool_use",
            content=[
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "submit_recommendations",
                    "input": payload,
                }
            ],
            text=None,
            tool_uses=[ToolUseCall(id="toolu_1", name="submit_recommendations", input=payload)],
            usage=_USAGE,
        )
    ]


def test_advice_endpoint_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/ai/financial-advisor/advice", json={})
    assert response.status_code == 401


def test_advice_endpoint_returns_recommendations(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    fake_provider = FakeAIProvider(db_session, _submit_only_script())
    fastapi_app.dependency_overrides[get_ai_provider] = lambda: fake_provider
    fastapi_app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()

    response = client.post(
        "/api/v1/ai/financial-advisor/advice",
        json={"message": "How am I doing?"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"][0]["title"] == "Connect an account to get started"


def test_list_recommendations_endpoint(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    fake_provider = FakeAIProvider(db_session, _submit_only_script())
    fastapi_app.dependency_overrides[get_ai_provider] = lambda: fake_provider
    fastapi_app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client.post("/api/v1/ai/financial-advisor/advice", json={}, headers=auth_headers)

    response = client.get("/api/v1/ai/recommendations", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "active"


def test_unknown_agent_slug_returns_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/v1/ai/not-a-real-agent/advice", json={}, headers=auth_headers)
    assert response.status_code == 404


def test_list_agents_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/ai/agents")

    assert response.status_code == 200
    assert response.json() == sorted(
        [
            "financial-advisor",
            "expense-analyst",
            "budget-coach",
            "retirement-planner",
            "tax-advisor",
            "fraud-detection",
            "investment-analyst",
            "portfolio-risk-analyst",
        ]
    )


def test_advice_endpoint_dispatches_to_the_requested_agent(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    fake_provider = FakeAIProvider(db_session, _submit_only_script())
    fastapi_app.dependency_overrides[get_ai_provider] = lambda: fake_provider
    fastapi_app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()

    response = client.post(
        "/api/v1/ai/expense-analyst/advice",
        json={"message": "How's my spending?"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    recommendations = client.get("/api/v1/ai/recommendations", headers=auth_headers).json()
    assert recommendations[0]["agent_name"] == "expense_analyst"
