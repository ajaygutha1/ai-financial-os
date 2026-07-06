import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User


def _txn(user_id: uuid.UUID, account_id: uuid.UUID, posted_at: date, amount: str) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        account_id=account_id,
        posted_at=posted_at,
        amount=Decimal(amount),
    )


def test_savings_rate_undefined_with_no_income(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/analytics/savings-rate", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["average_savings_rate"] is None
    assert body["months_with_income"] == 0
    assert all(m["savings_rate"] is None for m in body["months"])


def test_savings_rate_computed_when_income_present(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    today = date.today()
    db_session.add_all(
        [
            _txn(test_user.id, test_account.id, today, "4000"),
            _txn(test_user.id, test_account.id, today, "-3000"),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/savings-rate", params={"months": 1}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["months_with_income"] == 1
    assert Decimal(body["average_savings_rate"]) == Decimal("0.25")
    assert Decimal(body["months"][0]["savings_rate"]) == Decimal("0.25")
