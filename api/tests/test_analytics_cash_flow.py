import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.transaction import Transaction
from app.models.user import User


def _txn(
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    posted_at: date,
    amount: str,
    *,
    is_transfer: bool = False,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        account_id=account_id,
        posted_at=posted_at,
        amount=Decimal(amount),
        is_transfer=is_transfer,
    )


def test_cash_flow_empty(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/analytics/cash-flow", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["months"]) == 6
    assert Decimal(body["total_income"]) == Decimal("0")
    assert Decimal(body["total_expenses"]) == Decimal("0")


def test_cash_flow_classifies_by_account_type_and_excludes_transfers(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    today = date.today()
    credit_card = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Credit Card",
        account_type=AccountType.CREDIT_CARD.value,
        current_balance=Decimal("500"),
    )
    db_session.add(credit_card)
    db_session.flush()

    db_session.add_all(
        [
            _txn(test_user.id, test_account.id, today, "3000"),
            _txn(test_user.id, test_account.id, today, "-1200"),
            _txn(test_user.id, credit_card.id, today, "150"),
            _txn(
                test_user.id,
                test_account.id,
                today,
                "-1000",
                is_transfer=True,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/v1/analytics/cash-flow", params={"months": 1}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["months"]) == 1
    month = body["months"][0]
    assert Decimal(month["income"]) == Decimal("3000")
    # 1200 checking outflow + 150 credit-card charge; the transfer is excluded.
    assert Decimal(month["expenses"]) == Decimal("1350")
    assert Decimal(month["net"]) == Decimal("1650")
    assert month["transaction_count"] == 3
