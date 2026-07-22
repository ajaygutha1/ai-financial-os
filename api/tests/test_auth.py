from fastapi.testclient import TestClient

from app.models.user import User


def _csrf_header(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies["finos_csrf_token"]}


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

    refresh_response = client.post("/api/v1/auth/refresh", headers=_csrf_header(client))
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]


def test_refresh_without_cookie_fails(client: TestClient) -> None:
    # No refresh cookie at all -- rejected before the CSRF check even runs,
    # so this is a clean 401 rather than a confusing 403.
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


def test_refresh_without_csrf_header_is_rejected(client: TestClient, test_user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "correct-horse-battery"},
    )
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 403


def test_refresh_with_mismatched_csrf_header_is_rejected(
    client: TestClient, test_user: User
) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "correct-horse-battery"},
    )
    response = client.post(
        "/api/v1/auth/refresh", headers={"X-CSRF-Token": "not-the-real-token"}
    )
    assert response.status_code == 403


def test_me_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


def test_refresh_rotates_the_cookie_to_a_new_token(client: TestClient, test_user: User) -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "correct-horse-battery"},
    )
    original_cookie = login_response.cookies["finos_refresh_token"]

    refresh_response = client.post("/api/v1/auth/refresh", headers=_csrf_header(client))

    assert refresh_response.status_code == 200
    assert refresh_response.cookies["finos_refresh_token"] != original_cookie


def test_reusing_an_already_rotated_refresh_token_is_rejected(
    client: TestClient, test_user: User
) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "correct-horse-battery"},
    )
    original_cookie = client.cookies["finos_refresh_token"]

    first_refresh = client.post("/api/v1/auth/refresh", headers=_csrf_header(client))
    assert first_refresh.status_code == 200

    # Present the now-stale, already-rotated-away original token again --
    # simulates a copied/stolen refresh token being replayed.
    client.cookies.set("finos_refresh_token", original_cookie)
    reuse_response = client.post("/api/v1/auth/refresh", headers=_csrf_header(client))
    assert reuse_response.status_code == 401

    # The whole family was revoked as a consequence, so even the token that
    # *did* legitimately rotate (the one currently in the cookie jar from
    # first_refresh) is dead too -- both parties are forced to re-login.
    latest_cookie = first_refresh.cookies["finos_refresh_token"]
    client.cookies.set("finos_refresh_token", latest_cookie)
    follow_up = client.post("/api/v1/auth/refresh", headers=_csrf_header(client))
    assert follow_up.status_code == 401


def test_login_is_rate_limited_after_repeated_attempts(
    client: TestClient, test_user: User
) -> None:
    # Limit is 10/60s (app/routers/v1/auth.py) -- wrong-password attempts
    # count the same as successful ones, since the limiter runs before auth
    # is even checked.
    for _ in range(10):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "wrong-password"},
        )
        assert response.status_code == 401

    response = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "wrong-password"},
    )
    assert response.status_code == 429


def test_register_is_rate_limited_after_repeated_attempts(client: TestClient) -> None:
    # Limit is 5/60s -- each call uses a distinct email so it isn't the
    # duplicate-email 409 path being counted, just raw request volume.
    for i in range(5):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": f"ratelimit-{i}@example.com", "password": "s3cure-password"},
        )
        assert response.status_code == 201

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "ratelimit-overflow@example.com", "password": "s3cure-password"},
    )
    assert response.status_code == 429


def test_logout_without_csrf_header_is_rejected(client: TestClient, test_user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "correct-horse-battery"},
    )
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 403


def test_logout_without_a_session_is_a_no_op(client: TestClient) -> None:
    # Nothing to revoke and no CSRF cookie to check against -- clearing
    # already-absent cookies should not itself require a CSRF token.
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204


def test_logout_revokes_the_refresh_token_server_side(client: TestClient, test_user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "correct-horse-battery"},
    )
    # Captured before logout -- logout's Set-Cookie response clears these
    # from the client's own cookie jar, so this stands in for a copy having
    # been taken beforehand (a leaked/synced cookie jar, another device).
    token_before_logout = client.cookies["finos_refresh_token"]
    csrf_before_logout = client.cookies["finos_csrf_token"]

    logout_response = client.post("/api/v1/auth/logout", headers=_csrf_header(client))
    assert logout_response.status_code == 204

    client.cookies.set("finos_refresh_token", token_before_logout)
    client.cookies.set("finos_csrf_token", csrf_before_logout)
    response = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf_before_logout})
    assert response.status_code == 401
