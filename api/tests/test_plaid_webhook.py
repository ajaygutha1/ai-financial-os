import hashlib
import json
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from fastapi.testclient import TestClient
from jwt.algorithms import ECAlgorithm
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError
from app.core.plaid_webhook import verify_plaid_webhook
from app.ingestion.connectors.plaid.client import PlaidWebhookVerificationKey
from app.ingestion.connectors.plaid.dependency import get_plaid_client
from app.ingestion.connectors.plaid.fake_client import FakePlaidClient
from app.main import app as fastapi_app
from app.models.account import Account, AccountType
from app.models.connector_credential import ConnectorCredential
from app.models.user import User

KEY_ID = "test-key-1"


def _make_keypair() -> tuple[EllipticCurvePrivateKey, dict[str, str]]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_jwk = json.loads(ECAlgorithm(ECAlgorithm.SHA256).to_jwk(private_key.public_key()))
    public_jwk["kid"] = KEY_ID
    return private_key, public_jwk


def _sign_webhook(
    private_key: EllipticCurvePrivateKey, body: bytes, *, iat: float | None = None
) -> str:
    claims = {
        "iat": int(iat if iat is not None else time.time()),
        "request_body_sha256": hashlib.sha256(body).hexdigest(),
    }
    return jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": KEY_ID})


def test_verify_plaid_webhook_accepts_a_correctly_signed_request() -> None:
    private_key, public_jwk = _make_keypair()
    body = json.dumps({"webhook_type": "TRANSACTIONS", "item_id": "item-1"}).encode()
    token = _sign_webhook(private_key, body)
    client = FakePlaidClient(webhook_key=PlaidWebhookVerificationKey(key_id=KEY_ID, jwk=public_jwk))

    claims = verify_plaid_webhook(body=body, verification_header=token, plaid_client=client)

    assert claims["request_body_sha256"] == hashlib.sha256(body).hexdigest()


def test_verify_plaid_webhook_rejects_a_missing_header() -> None:
    client = FakePlaidClient()
    with pytest.raises(ForbiddenError, match="Missing"):
        verify_plaid_webhook(body=b"{}", verification_header=None, plaid_client=client)


def test_verify_plaid_webhook_rejects_a_tampered_body() -> None:
    private_key, public_jwk = _make_keypair()
    body = b'{"a": 1}'
    token = _sign_webhook(private_key, body)
    client = FakePlaidClient(webhook_key=PlaidWebhookVerificationKey(key_id=KEY_ID, jwk=public_jwk))

    with pytest.raises(ForbiddenError, match="body hash"):
        verify_plaid_webhook(body=b'{"a": 2}', verification_header=token, plaid_client=client)


def test_verify_plaid_webhook_rejects_a_stale_jwt() -> None:
    private_key, public_jwk = _make_keypair()
    body = b"{}"
    token = _sign_webhook(private_key, body, iat=time.time() - 3600)
    client = FakePlaidClient(webhook_key=PlaidWebhookVerificationKey(key_id=KEY_ID, jwk=public_jwk))

    with pytest.raises(ForbiddenError, match="stale"):
        verify_plaid_webhook(body=body, verification_header=token, plaid_client=client)


def test_verify_plaid_webhook_rejects_a_signature_from_the_wrong_key() -> None:
    private_key, _ = _make_keypair()
    _, wrong_public_jwk = _make_keypair()
    body = b"{}"
    token = _sign_webhook(private_key, body)
    client = FakePlaidClient(
        webhook_key=PlaidWebhookVerificationKey(key_id=KEY_ID, jwk=wrong_public_jwk)
    )

    with pytest.raises(ForbiddenError, match="signature verification failed"):
        verify_plaid_webhook(body=body, verification_header=token, plaid_client=client)


def test_verify_plaid_webhook_rejects_a_malformed_header() -> None:
    client = FakePlaidClient()
    with pytest.raises(ForbiddenError, match="Malformed"):
        verify_plaid_webhook(body=b"{}", verification_header="not-a-jwt", plaid_client=client)


def _webhook_body(*, item_id: str, webhook_code: str = "SYNC_UPDATES_AVAILABLE") -> bytes:
    return json.dumps(
        {"webhook_type": "TRANSACTIONS", "webhook_code": webhook_code, "item_id": item_id}
    ).encode()


def test_webhook_endpoint_rejects_an_unsigned_request(client: TestClient) -> None:
    response = client.post("/api/v1/connectors/plaid/webhook", content=_webhook_body(item_id="x"))
    assert response.status_code == 403


def test_webhook_endpoint_triggers_a_resync_for_a_known_item(
    client: TestClient,
    db_session: Session,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, public_jwk = _make_keypair()
    body = _webhook_body(item_id="item-known")

    credential = ConnectorCredential(
        user_id=test_user.id,
        provider="plaid",
        external_item_id="item-known",
        access_token_enc="access-sandbox-1",
    )
    db_session.add(credential)
    db_session.commit()
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Linked Checking",
        account_type=AccountType.CHECKING.value,
        current_balance=0,
        source="plaid",
        external_account_id="ext-1",
        connector_credential_id=credential.id,
    )
    db_session.add(account)
    db_session.commit()

    fake_plaid = FakePlaidClient(
        webhook_key=PlaidWebhookVerificationKey(key_id=KEY_ID, jwk=public_jwk)
    )
    fastapi_app.dependency_overrides[get_plaid_client] = lambda: fake_plaid

    enqueued: list[str] = []
    monkeypatch.setattr(
        "app.routers.v1.connectors.sync_account.delay",
        lambda account_id: enqueued.append(account_id),
    )

    token = _sign_webhook(private_key, body)
    response = client.post(
        "/api/v1/connectors/plaid/webhook",
        content=body,
        headers={"Plaid-Verification": token, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert enqueued == [str(account.id)]


def test_webhook_endpoint_ignores_an_unknown_item(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, public_jwk = _make_keypair()
    body = _webhook_body(item_id="item-does-not-exist")

    fake_plaid = FakePlaidClient(
        webhook_key=PlaidWebhookVerificationKey(key_id=KEY_ID, jwk=public_jwk)
    )
    fastapi_app.dependency_overrides[get_plaid_client] = lambda: fake_plaid

    enqueued: list[str] = []
    monkeypatch.setattr(
        "app.routers.v1.connectors.sync_account.delay",
        lambda account_id: enqueued.append(account_id),
    )

    token = _sign_webhook(private_key, body)
    response = client.post(
        "/api/v1/connectors/plaid/webhook",
        content=body,
        headers={"Plaid-Verification": token, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert enqueued == []


def test_webhook_endpoint_ignores_a_non_resync_webhook_code(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, public_jwk = _make_keypair()
    body = _webhook_body(item_id="item-known", webhook_code="DEFAULT_UPDATE")

    fake_plaid = FakePlaidClient(
        webhook_key=PlaidWebhookVerificationKey(key_id=KEY_ID, jwk=public_jwk)
    )
    fastapi_app.dependency_overrides[get_plaid_client] = lambda: fake_plaid

    token = _sign_webhook(private_key, body)
    response = client.post(
        "/api/v1/connectors/plaid/webhook",
        content=body,
        headers={"Plaid-Verification": token, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
