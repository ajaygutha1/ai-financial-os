import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ValidationError
from app.ingestion.connectors.ofx import OfxConnector
from app.models.account import Account

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample.ofx"


def _sample_ofx_bytes() -> bytes:
    return FIXTURE_PATH.read_bytes()


def test_ofx_connector_parses_accounts_and_transactions() -> None:
    connector = OfxConnector(_sample_ofx_bytes())

    accounts = connector.fetch_accounts()
    assert len(accounts) == 1
    assert accounts[0].account_type == "checking"
    assert accounts[0].current_balance == 3457.50

    transactions, cursor = connector.fetch_transactions(cursor=None)
    assert cursor is None
    assert len(transactions) == 2
    assert transactions[0].external_transaction_id == "OFX-TXN-001"
    assert transactions[0].amount == -42.50
    assert transactions[1].amount == 2500.00


def test_ofx_connector_rejects_invalid_content() -> None:
    with pytest.raises(ValidationError):
        OfxConnector(b"not an ofx file")


def _upload(client: TestClient, headers: dict[str, str], account_id: uuid.UUID, content: bytes):
    return client.post(
        "/api/v1/imports/ofx",
        headers=headers,
        data={"account_id": str(account_id)},
        files={"file": ("statement.ofx", content, "application/x-ofx")},
    )


def test_ofx_import_creates_transactions(
    client: TestClient, auth_headers: dict[str, str], test_account: Account
) -> None:
    response = _upload(client, auth_headers, test_account.id, _sample_ofx_bytes())

    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 2
    assert body["duplicate_count"] == 0

    list_response = client.get("/api/v1/transactions", headers=auth_headers)
    assert list_response.json()["total"] == 2


def test_ofx_import_detects_duplicates_on_reupload(
    client: TestClient, auth_headers: dict[str, str], test_account: Account
) -> None:
    first = _upload(client, auth_headers, test_account.id, _sample_ofx_bytes())
    assert first.json()["imported_count"] == 2

    second = _upload(client, auth_headers, test_account.id, _sample_ofx_bytes())
    body = second.json()
    assert body["duplicate_count"] == 2
    assert body["imported_count"] == 0

    # Unlike CSV's heuristic duplicates (persisted-but-flagged), connector
    # hard-identity duplicates (matched by external_transaction_id) are
    # skipped entirely -- the total stays at 2, not 4.
    list_response = client.get("/api/v1/transactions", headers=auth_headers)
    assert list_response.json()["total"] == 2


def test_ofx_import_requires_owned_account(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = _upload(client, auth_headers, uuid.uuid4(), _sample_ofx_bytes())
    assert response.status_code == 404


def test_ofx_import_requires_auth(client: TestClient, test_account: Account) -> None:
    response = client.post(
        "/api/v1/imports/ofx",
        data={"account_id": str(test_account.id)},
        files={"file": ("statement.ofx", _sample_ofx_bytes(), "application/x-ofx")},
    )
    assert response.status_code == 401
