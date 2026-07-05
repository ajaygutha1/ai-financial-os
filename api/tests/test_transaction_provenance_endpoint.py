import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User

SIMPLE_CSV = b"Date,Description,Amount\n2026-01-05,Starbucks Coffee,-4.75\n"


def test_get_provenance_for_owned_transaction(
    client: TestClient, auth_headers: dict[str, str], db_session: Session, test_account: Account
) -> None:
    client.post(
        "/api/v1/imports/csv",
        headers=auth_headers,
        data={"account_id": str(test_account.id), "debit_positive": "false"},
        files={"file": ("t.csv", SIMPLE_CSV, "text/csv")},
    )
    transaction = db_session.scalar(
        select(Transaction).where(Transaction.account_id == test_account.id)
    )
    assert transaction is not None

    response = client.get(f"/api/v1/transactions/{transaction.id}/provenance", headers=auth_headers)

    assert response.status_code == 200
    steps = {entry["step"] for entry in response.json()}
    assert "merchant_normalized" in steps
    assert "merchant_resolved" in steps


def test_get_provenance_requires_auth(client: TestClient) -> None:
    response = client.get(f"/api/v1/transactions/{uuid.uuid4()}/provenance")
    assert response.status_code == 401


def test_get_provenance_not_found_for_unowned_transaction(
    client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user: User
) -> None:
    other_user = User(
        id=uuid.uuid4(),
        email="other-provenance@example.com",
        hashed_password=None,
        is_verified=True,
    )
    db_session.add(other_user)
    db_session.commit()

    other_account = Account(
        id=uuid.uuid4(),
        user_id=other_user.id,
        name="Other Account",
        account_type="checking",
        current_balance=0,
    )
    db_session.add(other_account)
    db_session.commit()

    other_transaction = Transaction(
        id=uuid.uuid4(),
        user_id=other_user.id,
        account_id=other_account.id,
        posted_at=date(2026, 1, 1),
        amount=-10,
    )
    db_session.add(other_transaction)
    db_session.commit()

    response = client.get(
        f"/api/v1/transactions/{other_transaction.id}/provenance", headers=auth_headers
    )
    assert response.status_code == 404
