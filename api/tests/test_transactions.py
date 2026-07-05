import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User


def _make_transaction(user_id: uuid.UUID, account_id: uuid.UUID, days_ago: int) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        account_id=account_id,
        posted_at=date.today() - timedelta(days=days_ago),
        amount=Decimal("-42.50"),
        description="Test Merchant",
        merchant_normalized="Test Merchant",
    )


def test_list_transactions_empty(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/transactions", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_list_transactions_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/transactions")
    assert response.status_code == 401


def test_list_transactions_returns_seeded_rows(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    db_session.add_all(
        [_make_transaction(test_user.id, test_account.id, days_ago=i) for i in range(3)]
    )
    db_session.commit()

    response = client.get("/api/v1/transactions", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    # newest first
    assert body["items"][0]["posted_at"] == date.today().isoformat()


def test_list_transactions_pagination(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    db_session.add_all(
        [_make_transaction(test_user.id, test_account.id, days_ago=i) for i in range(5)]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/transactions", params={"page": 1, "page_size": 2}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_list_transactions_filters_by_account(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    other_account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Other Account",
        account_type="savings",
        current_balance=0,
    )
    db_session.add(other_account)
    db_session.add(_make_transaction(test_user.id, test_account.id, days_ago=0))
    db_session.add(_make_transaction(test_user.id, other_account.id, days_ago=0))
    db_session.commit()

    response = client.get(
        "/api/v1/transactions",
        params={"account_id": str(test_account.id)},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["account_id"] == str(test_account.id)
