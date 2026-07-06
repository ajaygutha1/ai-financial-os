import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.transaction import Transaction
from app.models.user import User


def test_debt_payoff_empty_with_no_liability_accounts(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/analytics/debt-payoff", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["accounts"] == []


def test_debt_payoff_on_track_projects_months_remaining(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
) -> None:
    credit_card = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Credit Card",
        account_type=AccountType.CREDIT_CARD.value,
        current_balance=Decimal("600"),
    )
    db_session.add(credit_card)
    db_session.flush()

    db_session.add(
        Transaction(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=credit_card.id,
            posted_at=date.today(),
            amount=Decimal("-300"),  # a payment reduces what's owed
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/debt-payoff", params={"months": 1}, headers=auth_headers
    )

    assert response.status_code == 200
    accounts = response.json()["accounts"]
    assert len(accounts) == 1
    projection = accounts[0]
    assert Decimal(projection["net_monthly_paydown"]) == Decimal("300")
    assert Decimal(projection["months_to_payoff"]) == Decimal("2")
    assert projection["on_track"] is True


def test_debt_payoff_not_on_track_when_balance_growing(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
) -> None:
    credit_card = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Credit Card",
        account_type=AccountType.CREDIT_CARD.value,
        current_balance=Decimal("600"),
    )
    db_session.add(credit_card)
    db_session.flush()

    db_session.add(
        Transaction(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=credit_card.id,
            posted_at=date.today(),
            amount=Decimal("300"),  # a new charge, increasing what's owed
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/debt-payoff", params={"months": 1}, headers=auth_headers
    )

    assert response.status_code == 200
    projection = response.json()["accounts"][0]
    assert projection["on_track"] is False
    assert projection["months_to_payoff"] is None
