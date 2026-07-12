import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analytics.common import add_months, month_start
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User


def _charge(
    user_id: uuid.UUID, account_id: uuid.UUID, posted_at: date, amount: str, merchant: str
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        account_id=account_id,
        posted_at=posted_at,
        amount=Decimal(amount),
        merchant_normalized=merchant,
    )


def test_subscriptions_empty(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/analytics/subscriptions", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["subscriptions"] == []


def test_subscriptions_detects_consistent_monthly_merchant_only(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    this_month = month_start(date.today())
    rows = []
    # Three fully-elapsed prior months (never "today", so day offsets are
    # always in the past regardless of what day of the month tests run).
    for i in range(1, 4):
        m = add_months(this_month, -i) + timedelta(days=5)
        rows.append(_charge(test_user.id, test_account.id, m, "-15.99", "NETFLIX"))

    # A one-off purchase from a different merchant, seen only once -- must not
    # be flagged (below MIN_OCCURRENCES).
    rows.append(_charge(test_user.id, test_account.id, date.today(), "-80", "BEST BUY"))

    # Two charges from the same merchant with wildly different amounts --
    # coincidental, not a subscription, must not be flagged.
    rows.append(
        _charge(
            test_user.id,
            test_account.id,
            add_months(this_month, -1) + timedelta(days=12),
            "-20",
            "RANDOM SHOP",
        )
    )
    rows.append(_charge(test_user.id, test_account.id, date.today(), "-200", "RANDOM SHOP"))

    db_session.add_all(rows)
    db_session.commit()

    response = client.get("/api/v1/analytics/subscriptions", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    merchants = {s["merchant"]: s for s in body["subscriptions"]}
    assert "NETFLIX" in merchants
    assert merchants["NETFLIX"]["cadence"] == "monthly"
    assert Decimal(merchants["NETFLIX"]["average_amount"]) == Decimal("15.99")
    assert "BEST BUY" not in merchants
    assert "RANDOM SHOP" not in merchants
    assert Decimal(body["estimated_monthly_total"]) == Decimal("15.99")
