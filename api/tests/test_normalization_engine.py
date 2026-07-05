import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.transaction import Transaction
from app.models.transaction_provenance import TransactionProvenance
from app.models.user import User

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample.ofx"


def _upload_csv(client: TestClient, headers: dict[str, str], account_id: uuid.UUID, content: bytes):
    return client.post(
        "/api/v1/imports/csv",
        headers=headers,
        data={"account_id": str(account_id), "debit_positive": "false"},
        files={"file": ("transactions.csv", content, "text/csv")},
    )


def test_transfer_detected_for_later_arriving_leg(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    savings = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Savings",
        account_type=AccountType.SAVINGS.value,
        current_balance=0,
    )
    db_session.add(savings)
    db_session.commit()

    # First leg lands with nothing to match against yet -- stays a plain purchase.
    outflow = _upload_csv(
        client,
        auth_headers,
        test_account.id,
        b"Date,Description,Amount\n2026-03-01,Transfer to Savings,-500.00\n",
    )
    assert outflow.status_code == 200

    # Second leg, in a different account, finds the equal-and-opposite match.
    inflow = _upload_csv(
        client,
        auth_headers,
        savings.id,
        b"Date,Description,Amount\n2026-03-01,Transfer from Checking,500.00\n",
    )
    assert inflow.status_code == 200

    outflow_txn = db_session.scalar(
        select(Transaction).where(Transaction.account_id == test_account.id)
    )
    inflow_txn = db_session.scalar(select(Transaction).where(Transaction.account_id == savings.id))

    assert outflow_txn is not None and inflow_txn is not None
    assert outflow_txn.is_transfer is False
    assert outflow_txn.transaction_type == "purchase"
    assert inflow_txn.is_transfer is True
    assert inflow_txn.transaction_type == "transfer"

    provenance = db_session.scalar(
        select(TransactionProvenance).where(
            TransactionProvenance.transaction_id == inflow_txn.id,
            TransactionProvenance.step == "transfer_detected",
        )
    )
    assert provenance is not None
    assert provenance.detail is not None
    assert provenance.detail["matched_transaction_id"] == str(outflow_txn.id)


def test_refund_detected_for_same_merchant(
    client: TestClient, auth_headers: dict[str, str], db_session: Session, test_account: Account
) -> None:
    _upload_csv(
        client,
        auth_headers,
        test_account.id,
        b"Date,Description,Amount\n2026-01-05,Starbucks Coffee,-4.75\n",
    )
    _upload_csv(
        client,
        auth_headers,
        test_account.id,
        b"Date,Description,Amount\n2026-01-10,Starbucks Refund,4.75\n",
    )

    transactions = list(db_session.scalars(select(Transaction).order_by(Transaction.posted_at)))
    assert len(transactions) == 2
    assert transactions[0].transaction_type == "purchase"
    assert transactions[1].transaction_type == "refund"

    provenance = db_session.scalar(
        select(TransactionProvenance).where(
            TransactionProvenance.transaction_id == transactions[1].id,
            TransactionProvenance.step == "refund_detected",
        )
    )
    assert provenance is not None


def test_wire_transfer_classified_via_description(
    client: TestClient, auth_headers: dict[str, str], db_session: Session, test_account: Account
) -> None:
    response = _upload_csv(
        client,
        auth_headers,
        test_account.id,
        b"Date,Description,Amount\n2026-04-01,WIRE TRANSFER TO JOHN DOE,-1000.00\n",
    )
    assert response.status_code == 200

    txn = db_session.scalar(select(Transaction).where(Transaction.account_id == test_account.id))
    assert txn is not None
    assert txn.transaction_type == "transfer"
    assert txn.is_transfer is True

    provenance = db_session.scalar(
        select(TransactionProvenance).where(
            TransactionProvenance.transaction_id == txn.id,
            TransactionProvenance.step == "ach_wire_classified",
        )
    )
    assert provenance is not None
    assert provenance.detail == {"channel": "wire"}


def test_currency_conversion_provenance_recorded_on_mismatch(
    client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user: User
) -> None:
    eur_account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="EUR Account",
        account_type=AccountType.CHECKING.value,
        current_balance=0,
        currency="EUR",
    )
    db_session.add(eur_account)
    db_session.commit()

    response = client.post(
        "/api/v1/imports/ofx",
        headers=auth_headers,
        data={"account_id": str(eur_account.id)},
        files={"file": ("statement.ofx", FIXTURE_PATH.read_bytes(), "application/x-ofx")},
    )
    assert response.status_code == 200

    txn = db_session.scalar(select(Transaction).where(Transaction.account_id == eur_account.id))
    assert txn is not None

    provenance = db_session.scalar(
        select(TransactionProvenance).where(
            TransactionProvenance.transaction_id == txn.id,
            TransactionProvenance.step == "currency_converted",
        )
    )
    assert provenance is not None
    assert provenance.detail is not None
    assert provenance.detail["original_currency"] == "USD"
    assert provenance.detail["converted_currency"] == "EUR"
    assert provenance.detail["conversion_available"] is True
