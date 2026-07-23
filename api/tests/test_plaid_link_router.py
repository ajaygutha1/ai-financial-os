from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.connectors.plaid.client import PlaidAccountData
from app.ingestion.connectors.plaid.dependency import get_plaid_client
from app.ingestion.connectors.plaid.fake_client import FakePlaidClient
from app.main import app as fastapi_app
from app.models.account import Account, AccountType
from app.models.connector_credential import ConnectorCredential
from app.models.user import User

ACCESS_TOKEN = "access-sandbox-xyz"
ITEM_ID = "item-xyz"


def _plaid_account(external_account_id: str = "plaid-acc-1") -> PlaidAccountData:
    return PlaidAccountData(
        external_account_id=external_account_id,
        name="Plaid Checking",
        account_type=AccountType.CHECKING.value,
        account_subtype="checking",
        currency="USD",
        current_balance=Decimal("2500.00"),
        available_balance=Decimal("2400.00"),
        mask="1234",
    )


def test_link_token_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/connectors/plaid/link-token")
    assert response.status_code == 401


def test_link_token_returns_a_token(client: TestClient, auth_headers: dict[str, str]) -> None:
    fake_client = FakePlaidClient(link_token="link-sandbox-abc")
    fastapi_app.dependency_overrides[get_plaid_client] = lambda: fake_client

    response = client.post("/api/v1/connectors/plaid/link-token", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["link_token"] == "link-sandbox-abc"


def test_exchange_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/connectors/plaid/exchange", json={"public_token": "public-x"})
    assert response.status_code == 401


def test_exchange_creates_credential_and_account(
    client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user: User
) -> None:
    fake_client = FakePlaidClient(
        accounts_by_token={ACCESS_TOKEN: [_plaid_account()]},
        exchange_result=(ACCESS_TOKEN, ITEM_ID),
    )
    fastapi_app.dependency_overrides[get_plaid_client] = lambda: fake_client

    response = client.post(
        "/api/v1/connectors/plaid/exchange",
        headers=auth_headers,
        json={"public_token": "public-sandbox-token", "institution_name": "Sandbox Bank"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["accounts"]) == 1
    assert body["accounts"][0]["institution_name"] == "Sandbox Bank"
    assert body["accounts"][0]["current_balance"] == "2500.0000"

    credential = db_session.scalar(
        select(ConnectorCredential).where(ConnectorCredential.external_item_id == ITEM_ID)
    )
    assert credential is not None
    assert credential.user_id == test_user.id
    # Encrypted at rest (Milestone 8's EncryptedString) -- reading it back
    # through the ORM transparently decrypts to the real access token.
    assert credential.access_token_enc == ACCESS_TOKEN

    account = db_session.scalar(
        select(Account).where(Account.connector_credential_id == credential.id)
    )
    assert account is not None
    assert account.external_account_id == "plaid-acc-1"
    assert account.source == "plaid"


def test_exchange_is_idempotent_for_the_same_item(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    fake_client = FakePlaidClient(
        accounts_by_token={ACCESS_TOKEN: [_plaid_account()]},
        exchange_result=(ACCESS_TOKEN, ITEM_ID),
    )
    fastapi_app.dependency_overrides[get_plaid_client] = lambda: fake_client

    first = client.post(
        "/api/v1/connectors/plaid/exchange",
        headers=auth_headers,
        json={"public_token": "public-1", "institution_name": "Sandbox Bank"},
    )
    second = client.post(
        "/api/v1/connectors/plaid/exchange",
        headers=auth_headers,
        json={"public_token": "public-2", "institution_name": "Sandbox Bank"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["accounts"][0]["id"] == second.json()["accounts"][0]["id"]

    credentials = db_session.scalars(
        select(ConnectorCredential).where(ConnectorCredential.external_item_id == ITEM_ID)
    ).all()
    assert len(credentials) == 1
