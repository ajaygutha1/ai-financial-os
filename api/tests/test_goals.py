import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.user import User


def test_create_goal_with_manual_tracking(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/goals",
        headers=auth_headers,
        json={
            "name": "Vacation fund",
            "target_amount": "2000.00",
            "manual_current_amount": "500.00",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Vacation fund"
    assert body["current_amount"] == "500.0000"
    assert body["progress_pct"] == "25.0000"
    assert body["status"] == "active"


def test_create_goal_linked_to_own_account_tracks_live_balance(
    client: TestClient, auth_headers: dict[str, str], test_account: Account
) -> None:
    response = client.post(
        "/api/v1/goals",
        headers=auth_headers,
        json={
            "name": "Emergency fund",
            "target_amount": "1000.00",
            "linked_account_id": str(test_account.id),
        },
    )

    assert response.status_code == 201
    body = response.json()
    # test_account's current_balance (1000), not manual_current_amount.
    assert body["current_amount"] == "1000.0000"
    assert body["linked_account_id"] == str(test_account.id)


def test_create_goal_linked_to_another_users_account_is_rejected(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    other_user = User(
        id=uuid.uuid4(),
        email="other-goal-owner@example.com",
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

    response = client.post(
        "/api/v1/goals",
        headers=auth_headers,
        json={
            "name": "Sneaky goal",
            "target_amount": "100.00",
            "linked_account_id": str(other_account.id),
        },
    )
    assert response.status_code == 422


def test_create_goal_linked_to_nonexistent_account_is_rejected(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/goals",
        headers=auth_headers,
        json={
            "name": "Sneaky goal",
            "target_amount": "100.00",
            "linked_account_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 422


def test_create_goal_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/goals", json={"name": "No auth", "target_amount": "1.00"})
    assert response.status_code == 401


def test_list_goals_returns_only_own_goals(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    client.post(
        "/api/v1/goals",
        headers=auth_headers,
        json={"name": "Goal A", "target_amount": "100.00"},
    )

    response = client.get("/api/v1/goals", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Goal A"


def test_update_goal(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = client.post(
        "/api/v1/goals",
        headers=auth_headers,
        json={"name": "Original", "target_amount": "100.00"},
    ).json()

    response = client.patch(
        f"/api/v1/goals/{created['id']}",
        headers=auth_headers,
        json={"name": "Renamed", "manual_current_amount": "50.00"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["current_amount"] == "50.0000"


def test_update_goal_owned_by_another_user_is_not_found(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.patch(
        f"/api/v1/goals/{uuid.uuid4()}",
        headers=auth_headers,
        json={"name": "Hijack"},
    )
    assert response.status_code == 404


def test_delete_goal(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = client.post(
        "/api/v1/goals",
        headers=auth_headers,
        json={"name": "To delete", "target_amount": "100.00"},
    ).json()

    response = client.delete(f"/api/v1/goals/{created['id']}", headers=auth_headers)
    assert response.status_code == 204

    response = client.get(f"/api/v1/goals/{created['id']}", headers=auth_headers)
    assert response.status_code == 404


def test_create_goal_linked_account_rejects_nonzero_manual_amount(
    client: TestClient, auth_headers: dict[str, str], test_account: Account
) -> None:
    response = client.post(
        "/api/v1/goals",
        headers=auth_headers,
        json={
            "name": "Contradictory goal",
            "target_amount": "1000.00",
            "linked_account_id": str(test_account.id),
            "manual_current_amount": "50.00",
        },
    )
    assert response.status_code == 422


def test_update_goal_setting_linked_account_rejects_existing_nonzero_manual_amount(
    client: TestClient, auth_headers: dict[str, str], test_account: Account
) -> None:
    created = client.post(
        "/api/v1/goals",
        headers=auth_headers,
        json={
            "name": "Manually tracked",
            "target_amount": "1000.00",
            "manual_current_amount": "50.00",
        },
    ).json()

    response = client.patch(
        f"/api/v1/goals/{created['id']}",
        headers=auth_headers,
        json={"linked_account_id": str(test_account.id)},
    )
    assert response.status_code == 422


def test_update_goal_status_rejects_invalid_value(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = client.post(
        "/api/v1/goals",
        headers=auth_headers,
        json={"name": "Status test", "target_amount": "100.00"},
    ).json()

    # Regression: status was previously a plain `str` with no enum
    # constraint -- a bogus value either persisted uninterpreted or, past
    # the column's 16-char limit, threw an unhandled 500 instead of a clean
    # validation error.
    response = client.patch(
        f"/api/v1/goals/{created['id']}",
        headers=auth_headers,
        json={"status": "totally-not-a-real-status"},
    )
    assert response.status_code == 422

    unchanged = client.get(f"/api/v1/goals/{created['id']}", headers=auth_headers)
    assert unchanged.json()["status"] == "active"


def test_update_goal_status_accepts_valid_value(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = client.post(
        "/api/v1/goals",
        headers=auth_headers,
        json={"name": "Status test", "target_amount": "100.00"},
    ).json()

    response = client.patch(
        f"/api/v1/goals/{created['id']}",
        headers=auth_headers,
        json={"status": "completed"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_progress_pct_caps_at_100(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/goals",
        headers=auth_headers,
        json={
            "name": "Overshot",
            "target_amount": "100.00",
            "manual_current_amount": "500.00",
        },
    )

    assert response.status_code == 201
    assert response.json()["progress_pct"] == "100.0000"
