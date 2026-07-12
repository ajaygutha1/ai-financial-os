import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analytics.common import add_months, month_start
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User


def _expense(
    user_id: uuid.UUID, account_id: uuid.UUID, posted_at: date, amount: str
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        account_id=account_id,
        posted_at=posted_at,
        amount=Decimal(amount),
    )


def test_burn_rate_zero_with_no_data(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/analytics/burn-rate", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["average_monthly_burn"]) == Decimal("0")
    assert body["is_burning"] is False


def test_burn_rate_positive_when_spending_exceeds_income(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    this_month = month_start(date.today())
    # $600 pure expense, no income, in each of the trailing 2 months.
    db_session.add_all(
        [
            _expense(test_user.id, test_account.id, date.today(), "-600"),
            _expense(
                test_user.id,
                test_account.id,
                add_months(this_month, -1) + timedelta(days=5),
                "-600",
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/v1/analytics/burn-rate", params={"months": 2}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["average_monthly_burn"]) == Decimal("600")
    assert body["is_burning"] is True
