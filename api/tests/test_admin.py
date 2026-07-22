from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


def test_list_users_requires_admin_role(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/admin/users", headers=auth_headers)
    assert response.status_code == 403


def test_list_users_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 401


def test_admin_can_list_users(
    client: TestClient,
    admin_auth_headers: dict[str, str],
    admin_user: User,
    test_user: User,
) -> None:
    response = client.get("/api/v1/admin/users", headers=admin_auth_headers)
    assert response.status_code == 200
    emails = {row["email"] for row in response.json()}
    assert emails == {admin_user.email, test_user.email}


def test_admin_can_view_a_single_user(
    client: TestClient, admin_auth_headers: dict[str, str], test_user: User
) -> None:
    response = client.get(f"/api/v1/admin/users/{test_user.id}", headers=admin_auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == test_user.email


def test_admin_viewing_a_nonexistent_user_is_not_found(
    client: TestClient, admin_auth_headers: dict[str, str]
) -> None:
    import uuid

    response = client.get(f"/api/v1/admin/users/{uuid.uuid4()}", headers=admin_auth_headers)
    assert response.status_code == 404


def test_admin_can_deactivate_a_user(
    client: TestClient,
    admin_auth_headers: dict[str, str],
    auth_headers: dict[str, str],
    test_user: User,
    db_session: Session,
) -> None:
    response = client.post(
        f"/api/v1/admin/users/{test_user.id}/deactivate", headers=admin_auth_headers
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    db_session.refresh(test_user)
    assert test_user.is_active is False

    # The deactivated user's existing access token stops working immediately
    # (get_current_user re-checks is_active on every request).
    me_response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_response.status_code == 401

    # And they can no longer log back in.
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "correct-horse-battery"},
    )
    assert login_response.status_code == 401


def test_admin_cannot_deactivate_their_own_account(
    client: TestClient, admin_auth_headers: dict[str, str], admin_user: User
) -> None:
    response = client.post(
        f"/api/v1/admin/users/{admin_user.id}/deactivate", headers=admin_auth_headers
    )
    assert response.status_code == 422


def test_non_admin_cannot_deactivate_a_user(
    client: TestClient, auth_headers: dict[str, str], admin_user: User
) -> None:
    response = client.post(f"/api/v1/admin/users/{admin_user.id}/deactivate", headers=auth_headers)
    assert response.status_code == 403
