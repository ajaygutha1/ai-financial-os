import uuid

from fastapi.testclient import TestClient

from app.models.account import Account


def test_create_account(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "name": "Primary Checking",
            "account_type": "checking",
            "institution_name": "First Bank",
            "current_balance": "1500.00",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Primary Checking"
    assert body["source"] == "manual"
    assert body["current_balance"] == "1500.0000"


def test_create_account_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/v1/accounts",
        json={"name": "No Auth", "account_type": "checking"},
    )
    assert response.status_code == 401


def test_list_accounts_returns_only_own_accounts(
    client: TestClient, auth_headers: dict[str, str], test_account: Account
) -> None:
    response = client.get("/api/v1/accounts", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(test_account.id)


def test_get_account_by_id(
    client: TestClient, auth_headers: dict[str, str], test_account: Account
) -> None:
    response = client.get(f"/api/v1/accounts/{test_account.id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == str(test_account.id)


def test_get_account_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get(f"/api/v1/accounts/{uuid.uuid4()}", headers=auth_headers)
    assert response.status_code == 404


def test_get_account_owned_by_another_user_is_not_found(
    client: TestClient, auth_headers: dict[str, str], db_session, test_account: Account
) -> None:
    from app.models.user import User

    other_user = User(
        id=uuid.uuid4(),
        email="other@example.com",
        hashed_password=None,
        is_verified=True,
    )
    db_session.add(other_user)
    db_session.commit()

    other_account = Account(
        id=uuid.uuid4(),
        user_id=other_user.id,
        name="Someone Else's Account",
        account_type="checking",
        current_balance=0,
    )
    db_session.add(other_account)
    db_session.commit()

    response = client.get(f"/api/v1/accounts/{other_account.id}", headers=auth_headers)
    assert response.status_code == 404
