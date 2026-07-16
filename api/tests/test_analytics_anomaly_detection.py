import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User


def _charge(
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    posted_at: date,
    amount: str,
    *,
    merchant: str | None = None,
    category: str | None = None,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        account_id=account_id,
        posted_at=posted_at,
        amount=Decimal(amount),
        merchant_normalized=merchant,
        category=category,
    )


def test_anomaly_detection_empty_with_no_transactions(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/analytics/anomaly-detection", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["flags"] == []
    assert body["transactions_scanned"] == 0


def test_flags_possible_duplicate_charge(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    today = date.today()
    db_session.add_all(
        [
            _charge(
                test_user.id,
                test_account.id,
                today,
                "-45.00",
                merchant="coffee-shop",
                category="Dining",
            ),
            _charge(
                test_user.id,
                test_account.id,
                today - timedelta(days=1),
                "-45.00",
                merchant="coffee-shop",
                category="Dining",
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/anomaly-detection", params={"months": 2}, headers=auth_headers
    )

    assert response.status_code == 200
    flags = response.json()["flags"]
    assert len(flags) == 2
    assert all(f["reason"] == "possible_duplicate_charge" for f in flags)


def test_flags_unusual_amount_for_category(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    today = date.today()
    rows = [
        _charge(
            test_user.id,
            test_account.id,
            today - timedelta(days=i),
            "-50.00",
            merchant=f"grocer-{i}",
            category="Groceries",
        )
        for i in range(4)
    ]
    rows.append(
        _charge(
            test_user.id,
            test_account.id,
            today,
            "-500.00",
            merchant="grocer-outlier",
            category="Groceries",
        )
    )
    db_session.add_all(rows)
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/anomaly-detection", params={"months": 2}, headers=auth_headers
    )

    assert response.status_code == 200
    flags = response.json()["flags"]
    assert len(flags) == 1
    assert flags[0]["reason"] == "unusual_amount_for_category"
    assert flags[0]["merchant"] == "grocer-outlier"


def test_flags_new_merchant_large_amount(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    today = date.today()
    # Distinct categories per row so each has a single member -- leave-one-out
    # category average is 0 for all of them, which routes evaluation to the
    # new-merchant check instead of the category check.
    rows = [
        _charge(
            test_user.id,
            test_account.id,
            today - timedelta(days=i + 1),
            "-30.00",
            merchant=f"regular-{i}",
            category=f"cat-{i}",
        )
        for i in range(5)
    ]
    rows.append(
        _charge(
            test_user.id,
            test_account.id,
            today,
            "-500.00",
            merchant="suspicious-co",
            category="cat-new",
        )
    )
    db_session.add_all(rows)
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/anomaly-detection", params={"months": 2}, headers=auth_headers
    )

    assert response.status_code == 200
    flags = response.json()["flags"]
    assert len(flags) == 1
    assert flags[0]["reason"] == "new_merchant_large_amount"
    assert flags[0]["merchant"] == "suspicious-co"


def test_duplicate_charges_do_not_mask_a_genuine_category_outlier(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    # Regression: a large duplicate-flagged pair used to still count toward
    # the category baseline that unusual_amount_for_category compares
    # against, inflating the average enough to hide a real outlier. Without
    # the fix: baseline includes the $200/$200 duplicates -> leave-one-out
    # average for the $180 charge is (680-180)/7 ~= $71.43, so $180 is
    # *below* the 3x threshold (~$214) and goes unflagged. With the fix, the
    # duplicates are excluded first -> average is (280-180)/5 = $20, and
    # $180 (9x) clears the threshold.
    today = date.today()
    rows = [
        _charge(
            test_user.id,
            test_account.id,
            today - timedelta(days=10 + i),
            "-20.00",
            merchant=f"cafe-{i}",
            category="Dining",
        )
        for i in range(4)
    ]
    # A repeat merchant (so the outlier below can't be caught by the
    # new_merchant_large_amount check instead -- isolating the category
    # baseline specifically).
    rows.append(
        _charge(
            test_user.id,
            test_account.id,
            today - timedelta(days=20),
            "-20.00",
            merchant="regular-diner",
            category="Dining",
        )
    )
    rows.append(
        _charge(
            test_user.id,
            test_account.id,
            today,
            "-180.00",
            merchant="regular-diner",
            category="Dining",
        )
    )
    # The duplicate pair that must not pollute the baseline above.
    rows.append(
        _charge(
            test_user.id,
            test_account.id,
            today - timedelta(days=5),
            "-200.00",
            merchant="big-dup",
            category="Dining",
        )
    )
    rows.append(
        _charge(
            test_user.id,
            test_account.id,
            today - timedelta(days=4),
            "-200.00",
            merchant="big-dup",
            category="Dining",
        )
    )
    db_session.add_all(rows)
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/anomaly-detection", params={"months": 2}, headers=auth_headers
    )

    assert response.status_code == 200
    flags = response.json()["flags"]
    reasons_by_merchant = {f["merchant"]: f["reason"] for f in flags}
    assert reasons_by_merchant["big-dup"] == "possible_duplicate_charge"
    assert reasons_by_merchant["regular-diner"] == "unusual_amount_for_category"


def test_excludes_transfers_and_duplicates_from_scan(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    today = date.today()
    real = _charge(test_user.id, test_account.id, today, "-50.00", merchant="shop")
    db_session.add(real)
    db_session.flush()

    transfer = _charge(test_user.id, test_account.id, today, "-9000.00", merchant="shop")
    transfer.is_transfer = True
    duplicate = _charge(test_user.id, test_account.id, today, "-9000.00", merchant="shop")
    duplicate.is_duplicate_of = real.id
    db_session.add_all([transfer, duplicate])
    db_session.commit()

    response = client.get(
        "/api/v1/analytics/anomaly-detection", params={"months": 1}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transactions_scanned"] == 1
    assert body["flags"] == []
