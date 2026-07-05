from fastapi.testclient import TestClient

from app.models.user import User


def test_register_creates_user_and_returns_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "s3cure-password", "full_name": "New User"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert "finos_refresh_token" in response.cookies


def test_register_duplicate_email_fails(client: TestClient, test_user: User) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": test_user.email, "password": "s3cure-password"},
    )

    assert response.status_code == 409


def test_login_success(client: TestClient, test_user: User) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "correct-horse-battery"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_wrong_password_fails(client: TestClient, test_user: User) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_refresh_token_flow(client: TestClient, test_user: User) -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "correct-horse-battery"},
    )
    assert "finos_refresh_token" in login_response.cookies

    refresh_response = client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]


def test_refresh_without_cookie_fails(client: TestClient) -> None:
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


def test_me_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"
