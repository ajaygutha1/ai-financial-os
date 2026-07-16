import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analytics.common import add_months, month_start
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User


def test_forecast_with_no_history_projects_flat(
    client: TestClient, auth_headers: dict[str, str], test_account: Account
) -> None:
    response = client.get("/api/v1/analytics/forecast", params={"months": 1}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["average_monthly_net"]) == Decimal("0")
    assert len(body["projected_months"]) == 6
    # No net cash flow -> every projected month equals current net worth.
    assert Decimal(body["projected_months"][0]["projected_net_worth"]) == Decimal(
        body["current_net_worth"]
    )


def test_forecast_projects_net_worth_forward_using_average_net_flow(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    this_month = month_start(date.today())
    db_session.add(
        Transaction(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            posted_at=this_month,
            amount=Decimal("200"),  # net income this month
        )
    )
    db_session.commit()

    response = client.get("/api/v1/analytics/forecast", params={"months": 1}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["average_monthly_net"]) == Decimal("200")

    current_net_worth = Decimal(body["current_net_worth"])
    projected = body["projected_months"]
    assert len(projected) == 6
    assert Decimal(projected[0]["projected_net_worth"]) == current_net_worth + Decimal("200")
    assert Decimal(projected[5]["projected_net_worth"]) == current_net_worth + Decimal("1200")
    assert projected[0]["month"] == add_months(this_month, 1).isoformat()
