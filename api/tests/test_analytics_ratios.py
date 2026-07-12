import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.transaction import Transaction
from app.models.user import User


def test_ratios_all_none_with_no_income(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/analytics/ratios", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["savings_rate"] is None
    assert body["expense_to_income_ratio"] is None
    assert body["debt_to_annual_income"] is None


def test_ratios_computed_with_income_and_debt(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    credit_card = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Credit Card",
        account_type=AccountType.CREDIT_CARD.value,
        current_balance=Decimal("2400"),
    )
    db_session.add(credit_card)
    db_session.flush()

    today = date.today()
    db_session.add_all(
        [
            Transaction(
                id=uuid.uuid4(),
                user_id=test_user.id,
                account_id=test_account.id,
                posted_at=today,
                amount=Decimal("4000"),
            ),
            Transaction(
                id=uuid.uuid4(),
                user_id=test_user.id,
                account_id=test_account.id,
                posted_at=today,
                amount=Decimal("-3000"),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/v1/analytics/ratios", params={"months": 1}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["savings_rate"]) == Decimal("0.25")
    assert Decimal(body["expense_to_income_ratio"]) == Decimal("0.75")
    # annualized income = 4000 * 12 = 48000; liabilities = 2400 -> ratio = 0.05
    assert Decimal(body["debt_to_annual_income"]) == Decimal("0.05")
    # liquidity_ratio_months must honor the requested months=1 window, not
    # emergency_fund's own DEFAULT_MONTHS=3 -- test_account's balance (1000)
    # over 1 month of 3000 in expenses is 1/3 months of coverage; if ratios.py
    # silently called emergency_fund.compute() with no months kwarg, the
    # 3-month-average expense figure (1000, since the other 2 months are
    # zero-filled) would instead read as a full 1.0 months of coverage.
    assert Decimal(body["liquidity_ratio_months"]) == Decimal("1000") / Decimal("3000")
