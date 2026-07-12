import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User


def test_emergency_fund_unknown_with_no_expense_history(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/analytics/emergency-fund", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["months_of_coverage"] is None
    assert body["health_tier"] == "unknown"


def test_emergency_fund_tiering(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    # test_account (checking) has current_balance=1000.
    db_session.add(
        Transaction(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            posted_at=date.today(),
            amount=Decimal("-500"),
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/emergency-fund", params={"months": 1}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["liquid_assets"]) == Decimal("1000")
    assert Decimal(body["average_monthly_expenses"]) == Decimal("500")
    assert Decimal(body["months_of_coverage"]) == Decimal("2")
    assert body["health_tier"] == "low"
