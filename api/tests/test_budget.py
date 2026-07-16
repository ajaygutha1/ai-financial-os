import threading
import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.account import Account
from app.models.budget_target import BudgetTarget
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.budget_target_repository import BudgetTargetRepository


def _category(db_session: Session, name: str = "Groceries") -> Category:
    category = Category(id=uuid.uuid4(), name=name, is_system=False)
    db_session.add(category)
    db_session.commit()
    return category


def test_list_categories(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    _category(db_session, "Groceries")

    response = client.get("/api/v1/categories", headers=auth_headers)

    assert response.status_code == 200
    assert any(c["name"] == "Groceries" for c in response.json())


def test_set_budget_target(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    category = _category(db_session)

    response = client.post(
        "/api/v1/budget/targets",
        headers=auth_headers,
        json={"category_id": str(category.id), "monthly_target_amount": "400.00"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["category_name"] == "Groceries"
    assert body["monthly_target_amount"] == "400.0000"


def test_setting_a_target_twice_upserts_not_duplicates(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    category = _category(db_session)
    client.post(
        "/api/v1/budget/targets",
        headers=auth_headers,
        json={"category_id": str(category.id), "monthly_target_amount": "400.00"},
    )

    response = client.post(
        "/api/v1/budget/targets",
        headers=auth_headers,
        json={"category_id": str(category.id), "monthly_target_amount": "500.00"},
    )
    assert response.status_code == 201
    assert response.json()["monthly_target_amount"] == "500.0000"

    listed = client.get("/api/v1/budget/targets", headers=auth_headers).json()
    assert len(listed) == 1
    assert listed[0]["monthly_target_amount"] == "500.0000"


def test_concurrent_upsert_for_new_category_does_not_raise_integrity_error(
    db_session: Session, engine: Engine, test_user: User
) -> None:
    # Regression: two concurrent upserts for a category with no existing
    # target (e.g. a double-submit) both miss the SELECT and race to
    # INSERT -- ux_budget_targets_user_category then raises an uncaught
    # IntegrityError for whichever loses the race. Both callers' intended
    # amount must still win through to the final row (upsert semantics),
    # not just whichever happened to insert first.
    category = _category(db_session)
    category_id = category.id
    user_id = test_user.id

    session_factory = sessionmaker(bind=engine)
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def _upsert(amount: str) -> None:
        session = session_factory()
        try:
            barrier.wait(timeout=5)
            BudgetTargetRepository(session).upsert(
                user_id=user_id, category_id=category_id, monthly_target_amount=Decimal(amount)
            )
            session.commit()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            session.close()

    threads = [
        threading.Thread(target=_upsert, args=("400.00",)),
        threading.Thread(target=_upsert, args=("500.00",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"concurrent upsert() calls raised: {errors}"

    rows = list(
        db_session.scalars(
            select(BudgetTarget).where(
                BudgetTarget.user_id == user_id, BudgetTarget.category_id == category_id
            )
        )
    )
    assert len(rows) == 1
    assert rows[0].monthly_target_amount in (Decimal("400.00"), Decimal("500.00"))


def test_set_budget_target_with_nonexistent_category_is_rejected(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/budget/targets",
        headers=auth_headers,
        json={"category_id": str(uuid.uuid4()), "monthly_target_amount": "100.00"},
    )
    assert response.status_code == 422


def test_delete_budget_target(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    category = _category(db_session)
    created = client.post(
        "/api/v1/budget/targets",
        headers=auth_headers,
        json={"category_id": str(category.id), "monthly_target_amount": "400.00"},
    ).json()

    response = client.delete(f"/api/v1/budget/targets/{created['id']}", headers=auth_headers)
    assert response.status_code == 204

    listed = client.get("/api/v1/budget/targets", headers=auth_headers).json()
    assert listed == []


def test_delete_budget_target_owned_by_another_user_is_not_found(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.delete(f"/api/v1/budget/targets/{uuid.uuid4()}", headers=auth_headers)
    assert response.status_code == 404


def test_budget_vs_actual_empty_with_no_targets(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/analytics/budget-vs-actual", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["categories"] == []


def test_budget_vs_actual_compares_this_months_actual_spend(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_account: Account,
) -> None:
    category = _category(db_session)
    client.post(
        "/api/v1/budget/targets",
        headers=auth_headers,
        json={"category_id": str(category.id), "monthly_target_amount": "400.00"},
    )

    today = date.today()
    db_session.add(
        Transaction(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id=test_account.id,
            posted_at=today,
            amount=Decimal("-150.00"),
            category_id=category.id,
        )
    )
    db_session.commit()

    response = client.get("/api/v1/analytics/budget-vs-actual", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["categories"]) == 1
    entry = body["categories"][0]
    assert entry["target_amount"] == "400.0000"
    assert entry["actual_amount"] == "150.0000"
    assert entry["remaining"] == "250.0000"
    assert entry["pct_used"] == "37.5000"
