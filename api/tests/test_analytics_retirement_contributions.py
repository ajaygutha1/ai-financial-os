import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.transaction import Transaction
from app.models.user import User


def test_retirement_contributions_empty_with_no_retirement_accounts(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/analytics/retirement-contributions", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["account_count"] == 0
    assert Decimal(body["total_balance"]) == Decimal("0")


def test_retirement_contributions_averages_net_deposits(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
) -> None:
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="401k",
        account_type=AccountType.RETIREMENT.value,
        current_balance=Decimal("10000"),
    )
    db_session.add(account)
    db_session.flush()

    db_session.add(
        Transaction(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=account.id,
            posted_at=date.today(),
            amount=Decimal("500"),  # a contribution/growth, money in
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/retirement-contributions",
        params={"months": 1},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["account_count"] == 1
    assert Decimal(body["total_balance"]) == Decimal("10000")
    assert Decimal(body["average_monthly_contribution"]) == Decimal("500")


def test_retirement_contributions_excludes_transfers_and_duplicates(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
) -> None:
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="401k",
        account_type=AccountType.RETIREMENT.value,
        current_balance=Decimal("10000"),
    )
    db_session.add(account)
    db_session.flush()

    real_txn_id = uuid.uuid4()
    db_session.add_all(
        [
            Transaction(
                id=real_txn_id,
                user_id=test_user.id,
                account_id=account.id,
                posted_at=date.today(),
                amount=Decimal("500"),
            ),
            Transaction(
                id=uuid.uuid4(),
                user_id=test_user.id,
                account_id=account.id,
                posted_at=date.today(),
                amount=Decimal("500"),
                is_duplicate_of=real_txn_id,
            ),
            Transaction(
                id=uuid.uuid4(),
                user_id=test_user.id,
                account_id=account.id,
                posted_at=date.today(),
                amount=Decimal("1000"),
                is_transfer=True,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/retirement-contributions",
        params={"months": 1},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert Decimal(response.json()["average_monthly_contribution"]) == Decimal("500")
