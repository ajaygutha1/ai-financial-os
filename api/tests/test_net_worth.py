import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.user import User


def test_net_worth_zero_with_no_accounts(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/analytics/net-worth", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["net_worth"] == "0"
    assert body["assets_total"] == "0"
    assert body["liabilities_total"] == "0"


def test_net_worth_sums_assets_and_subtracts_liabilities(
    client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user: User
) -> None:
    db_session.add_all(
        [
            Account(
                id=uuid.uuid4(),
                user_id=test_user.id,
                name="Checking",
                account_type=AccountType.CHECKING.value,
                current_balance=5000,
            ),
            Account(
                id=uuid.uuid4(),
                user_id=test_user.id,
                name="Credit Card",
                account_type=AccountType.CREDIT_CARD.value,
                current_balance=1200,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/v1/analytics/net-worth", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["assets_total"] == "5000.0000"
    assert body["liabilities_total"] == "1200.0000"
    assert body["net_worth"] == "3800.0000"


def test_net_worth_ignores_inactive_accounts(
    client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user: User
) -> None:
    db_session.add(
        Account(
            id=uuid.uuid4(),
            user_id=test_user.id,
            name="Closed Account",
            account_type=AccountType.SAVINGS.value,
            current_balance=999,
            is_active=False,
        )
    )
    db_session.commit()

    response = client.get("/api/v1/analytics/net-worth", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["net_worth"] == "0"
