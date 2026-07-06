import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.ingestion.connectors.ofx import OfxConnector
from app.models.account import Account

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample.ofx"
MULTI_ACCOUNT_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_multi_account.ofx"


def _sample_ofx_bytes() -> bytes:
    return FIXTURE_PATH.read_bytes()


def _multi_account_ofx_bytes() -> bytes:
    return MULTI_ACCOUNT_FIXTURE_PATH.read_bytes()


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


def test_ofx_connector_rejects_multi_account_file_with_no_target_given() -> None:
    connector = OfxConnector(_multi_account_ofx_bytes())
    accounts = connector.fetch_accounts()
    assert len(accounts) == 2

    # No external_account_id to disambiguate -- must not silently pool both
    # statements' transactions together.
    with pytest.raises(ValidationError):
        connector.fetch_transactions(cursor=None)


def test_ofx_connector_filters_to_matching_statement_when_multiple_present() -> None:
    connector = OfxConnector(_multi_account_ofx_bytes())

    transactions, _ = connector.fetch_transactions(cursor=None, external_account_id="987654321")
    assert [t.external_transaction_id for t in transactions] == ["OFX-TXN-001", "OFX-TXN-002"]

    transactions, _ = connector.fetch_transactions(cursor=None, external_account_id="555555555")
    assert [t.external_transaction_id for t in transactions] == ["OFX-TXN-101"]


def test_ofx_connector_rejects_unmatched_target_in_multi_account_file() -> None:
    connector = OfxConnector(_multi_account_ofx_bytes())

    with pytest.raises(ValidationError):
        connector.fetch_transactions(cursor=None, external_account_id="does-not-exist")


def test_ofx_import_rejects_multi_account_file_for_unlinked_account(
    client: TestClient, auth_headers: dict[str, str], test_account: Account
) -> None:
    # test_account has no external_account_id set, so it can't be
    # disambiguated against a file containing two statements -- the import
    # must be rejected rather than silently pooling both accounts'
    # transactions into test_account.
    response = _upload(client, auth_headers, test_account.id, _multi_account_ofx_bytes())
    assert response.status_code == 422

    list_response = client.get("/api/v1/transactions", headers=auth_headers)
    assert list_response.json()["total"] == 0


def test_ofx_import_uses_matching_statement_for_linked_account(
    client: TestClient, auth_headers: dict[str, str], test_account: Account, db_session: Session
) -> None:
    test_account.external_account_id = "555555555"
    db_session.commit()

    response = _upload(client, auth_headers, test_account.id, _multi_account_ofx_bytes())
    assert response.status_code == 200
    assert response.json()["imported_count"] == 1

    list_response = client.get("/api/v1/transactions", headers=auth_headers)
    body = list_response.json()
    assert body["total"] == 1
    assert body["items"][0]["description"] == "Savings Interest"
