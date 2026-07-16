import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction, TransactionType
from app.models.user import User


def test_taxable_events_empty_with_no_transactions(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/analytics/taxable-events", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["dividend_count"] == 0
    assert Decimal(body["dividend_total"]) == Decimal("0")


def test_taxable_events_counts_and_sums_by_type(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    today = date.today()
    db_session.add_all(
        [
            Transaction(
                id=uuid.uuid4(),
                user_id=test_user.id,
                account_id=test_account.id,
                posted_at=today,
                amount=Decimal("50"),
                transaction_type=TransactionType.DIVIDEND.value,
            ),
            Transaction(
                id=uuid.uuid4(),
                user_id=test_user.id,
                account_id=test_account.id,
                posted_at=today,
                amount=Decimal("10"),
                transaction_type=TransactionType.INTEREST.value,
            ),
            Transaction(
                id=uuid.uuid4(),
                user_id=test_user.id,
                account_id=test_account.id,
                posted_at=today,
                amount=Decimal("-1000"),
                transaction_type=TransactionType.BUY.value,
            ),
            Transaction(
                id=uuid.uuid4(),
                user_id=test_user.id,
                account_id=test_account.id,
                posted_at=today,
                amount=Decimal("1200"),
                transaction_type=TransactionType.SELL.value,
            ),
            # Not a tracked type -- must not leak into any bucket.
            Transaction(
                id=uuid.uuid4(),
                user_id=test_user.id,
                account_id=test_account.id,
                posted_at=today,
                amount=Decimal("-25"),
                transaction_type=TransactionType.PURCHASE.value,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/taxable-events", params={"months": 1}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dividend_count"] == 1
    assert Decimal(body["dividend_total"]) == Decimal("50")
    assert body["interest_count"] == 1
    assert Decimal(body["interest_total"]) == Decimal("10")
    assert body["buy_count"] == 1
    assert Decimal(body["buy_total"]) == Decimal("1000")  # abs() of a negative buy amount
    assert body["sell_count"] == 1
    assert Decimal(body["sell_total"]) == Decimal("1200")


def test_taxable_events_excludes_duplicates_and_transfers(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    real_id = uuid.uuid4()
    db_session.add_all(
        [
            Transaction(
                id=real_id,
                user_id=test_user.id,
                account_id=test_account.id,
                posted_at=date.today(),
                amount=Decimal("50"),
                transaction_type=TransactionType.DIVIDEND.value,
            ),
            Transaction(
                id=uuid.uuid4(),
                user_id=test_user.id,
                account_id=test_account.id,
                posted_at=date.today(),
                amount=Decimal("50"),
                transaction_type=TransactionType.DIVIDEND.value,
                is_duplicate_of=real_id,
            ),
            Transaction(
                id=uuid.uuid4(),
                user_id=test_user.id,
                account_id=test_account.id,
                posted_at=date.today(),
                amount=Decimal("100"),
                transaction_type=TransactionType.DIVIDEND.value,
                is_transfer=True,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/taxable-events", params={"months": 1}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dividend_count"] == 1
    assert Decimal(body["dividend_total"]) == Decimal("50")
