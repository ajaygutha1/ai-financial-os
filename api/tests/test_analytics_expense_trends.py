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
    user_id: uuid.UUID, account_id: uuid.UUID, posted_at: date, amount: str, category: str
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        account_id=account_id,
        posted_at=posted_at,
        amount=Decimal(amount),
        category=category,
    )


def test_expense_trends_empty(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/analytics/expense-trends", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["categories"] == []


def test_expense_trends_flags_rising_and_steady_categories(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    this_month = month_start(date.today())
    rows = []
    for i in range(3):  # 3 prior months + current = 4 total with months=4
        m = add_months(this_month, -(i + 1))
        rows.append(
            _expense(test_user.id, test_account.id, m + timedelta(days=5), "-100", "Groceries")
        )
        rows.append(_expense(test_user.id, test_account.id, m + timedelta(days=6), "-1000", "Rent"))
    # Latest month: groceries spikes, rent stays flat
    today = date.today()
    rows.append(_expense(test_user.id, test_account.id, today, "-250", "Groceries"))
    rows.append(_expense(test_user.id, test_account.id, today, "-1000", "Rent"))
    db_session.add_all(rows)
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/expense-trends", params={"months": 4}, headers=auth_headers
    )

    assert response.status_code == 200
    by_category = {c["category"]: c for c in response.json()["categories"]}

    groceries = by_category["Groceries"]
    assert groceries["trend"] == "rising"
    assert Decimal(groceries["latest_month_total"]) == Decimal("250")
    assert Decimal(groceries["prior_average"]) == Decimal("100")

    rent = by_category["Rent"]
    assert rent["trend"] == "steady"
    assert Decimal(rent["latest_month_total"]) == Decimal("1000")
