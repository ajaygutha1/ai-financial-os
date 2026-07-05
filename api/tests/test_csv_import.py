import uuid

from fastapi.testclient import TestClient

from app.models.account import Account

SIMPLE_CSV = (
    b"Date,Description,Amount\n"
    b"2026-01-05,Starbucks Coffee,-4.75\n"
    b"2026-01-06,Amazon.com*AB12CD34,-89.99\n"
    b"2026-01-07,Payroll Deposit,2500.00\n"
)

CSV_WITH_BAD_ROW = (
    b"Date,Description,Amount\n2026-01-05,Good Row,-10.00\nnot-a-date,Bad Row,-5.00\n"
)


def _upload(
    client: TestClient,
    headers: dict[str, str],
    account_id: uuid.UUID,
    content: bytes,
    debit_positive: bool = False,
):
    return client.post(
        "/api/v1/imports/csv",
        headers=headers,
        data={"account_id": str(account_id), "debit_positive": str(debit_positive).lower()},
        files={"file": ("transactions.csv", content, "text/csv")},
    )


def test_csv_import_creates_transactions(
    client: TestClient, auth_headers: dict[str, str], test_account: Account
) -> None:
    response = _upload(client, auth_headers, test_account.id, SIMPLE_CSV)

    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 3
    assert body["duplicate_count"] == 0
    assert body["error_count"] == 0

    list_response = client.get("/api/v1/transactions", headers=auth_headers)
    assert list_response.json()["total"] == 3


def test_csv_import_normalizes_merchant_names(
    client: TestClient, auth_headers: dict[str, str], test_account: Account
) -> None:
    _upload(client, auth_headers, test_account.id, SIMPLE_CSV)

    list_response = client.get("/api/v1/transactions", headers=auth_headers)
    merchants = {item["merchant_normalized"] for item in list_response.json()["items"]}
    assert "Amazon" in merchants


def test_csv_import_detects_duplicates_on_reupload(
    client: TestClient, auth_headers: dict[str, str], test_account: Account
) -> None:
    first = _upload(client, auth_headers, test_account.id, SIMPLE_CSV)
    assert first.json()["imported_count"] == 3

    second = _upload(client, auth_headers, test_account.id, SIMPLE_CSV)
    body = second.json()
    assert body["duplicate_count"] == 3
    assert body["imported_count"] == 0

    list_response = client.get("/api/v1/transactions", headers=auth_headers)
    # duplicates are flagged, not dropped -- both batches are persisted
    assert list_response.json()["total"] == 6


def test_csv_import_flags_unparseable_rows_without_failing_whole_import(
    client: TestClient, auth_headers: dict[str, str], test_account: Account
) -> None:
    response = _upload(client, auth_headers, test_account.id, CSV_WITH_BAD_ROW)

    body = response.json()
    assert response.status_code == 200
    assert body["imported_count"] == 1
    assert body["error_count"] == 1
    assert "Row 3" in body["errors"][0]


def test_csv_import_requires_owned_account(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = _upload(client, auth_headers, uuid.uuid4(), SIMPLE_CSV)
    assert response.status_code == 404


def test_csv_import_requires_auth(client: TestClient, test_account: Account) -> None:
    response = client.post(
        "/api/v1/imports/csv",
        data={"account_id": str(test_account.id), "debit_positive": "false"},
        files={"file": ("transactions.csv", SIMPLE_CSV, "text/csv")},
    )
    assert response.status_code == 401
