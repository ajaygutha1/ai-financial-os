from app.core.config import get_settings
from app.ingestion.connectors.plaid.client import PlaidClient
from app.ingestion.connectors.plaid.real_client import RealPlaidClient


def get_plaid_client() -> PlaidClient:
    """FastAPI dependency (and plain callable for the Celery task, which has
    no DI container) -- overridden in tests with a FakePlaidClient. Routers
    and tasks depend on this instead of instantiating RealPlaidClient
    directly, matching get_ai_provider's pattern."""
    settings = get_settings()
    return RealPlaidClient(
        client_id=settings.plaid_client_id,
        secret=settings.plaid_secret,
        environment=settings.plaid_env,
    )
