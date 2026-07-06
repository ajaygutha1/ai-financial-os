import threading
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.account import Account
from app.models.category import Category
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.repositories.category_repository import CategoryRepository
from app.repositories.merchant_repository import MerchantRepository

CSV_WITH_KNOWN_MERCHANTS = (
    b"Date,Description,Amount\n"
    b"2026-01-05,Starbucks Coffee,-4.75\n"
    b"2026-01-06,Amazon.com*AB12CD34,-89.99\n"
)


def test_csv_import_resolves_merchant_and_category(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_account: Account,
) -> None:
    response = client.post(
        "/api/v1/imports/csv",
        headers=auth_headers,
        data={"account_id": str(test_account.id), "debit_positive": "false"},
        files={"file": ("transactions.csv", CSV_WITH_KNOWN_MERCHANTS, "text/csv")},
    )
    assert response.status_code == 200

    transactions = list(db_session.scalars(select(Transaction).order_by(Transaction.posted_at)))
    assert len(transactions) == 2
    for txn in transactions:
        assert txn.merchant_id is not None
        assert txn.category_id is not None

    starbucks = db_session.get(Merchant, transactions[0].merchant_id)
    assert starbucks is not None
    assert starbucks.canonical_name == "Starbucks"

    category = db_session.get(Category, starbucks.category_id)
    assert category is not None
    assert category.name == "Food & Dining"
    assert category.is_system is True


def test_merchant_row_is_reused_across_imports(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
    test_account: Account,
) -> None:
    csv_one = b"Date,Description,Amount\n2026-01-05,Starbucks Coffee,-4.75\n"
    csv_two = b"Date,Description,Amount\n2026-02-10,Starbucks Downtown,-6.10\n"

    client.post(
        "/api/v1/imports/csv",
        headers=auth_headers,
        data={"account_id": str(test_account.id), "debit_positive": "false"},
        files={"file": ("a.csv", csv_one, "text/csv")},
    )
    client.post(
        "/api/v1/imports/csv",
        headers=auth_headers,
        data={"account_id": str(test_account.id), "debit_positive": "false"},
        files={"file": ("b.csv", csv_two, "text/csv")},
    )

    merchants = list(
        db_session.scalars(select(Merchant).where(Merchant.canonical_name == "Starbucks"))
    )
    assert len(merchants) == 1

    transactions = list(db_session.scalars(select(Transaction).order_by(Transaction.posted_at)))
    assert len(transactions) == 2
    assert transactions[0].merchant_id == transactions[1].merchant_id


def test_concurrent_merchant_creation_does_not_raise_integrity_error(
    db_session: Session, engine: Engine
) -> None:
    # Two sessions racing to resolve a brand-new merchant name both miss on
    # the initial SELECT, then both attempt to INSERT -- exercising
    # ux_merchant_canonical_name_lower. Without the SAVEPOINT-and-retry in
    # MerchantRepository, the loser raises an uncaught IntegrityError instead
    # of returning the winner's row.
    session_factory = sessionmaker(bind=engine)
    barrier = threading.Barrier(2)
    results: list[uuid.UUID] = []
    errors: list[Exception] = []

    def _resolve() -> None:
        session = session_factory()
        try:
            barrier.wait(timeout=5)
            merchant = MerchantRepository(session).find_or_create_by_canonical_name(
                "Concurrent Test Merchant"
            )
            session.commit()
            results.append(merchant.id)  # read before close, while still attached
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=_resolve) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"concurrent merchant resolution raised: {errors}"
    assert len(results) == 2
    assert results[0] == results[1]

    all_matching = list(
        db_session.scalars(
            select(Merchant).where(Merchant.canonical_name == "Concurrent Test Merchant")
        )
    )
    assert len(all_matching) == 1


def test_concurrent_category_creation_does_not_raise_integrity_error(
    db_session: Session, engine: Engine
) -> None:
    session_factory = sessionmaker(bind=engine)
    barrier = threading.Barrier(2)
    results: list[uuid.UUID] = []
    errors: list[Exception] = []

    def _resolve() -> None:
        session = session_factory()
        try:
            barrier.wait(timeout=5)
            category = CategoryRepository(session).get_or_create("Concurrent Test Category")
            session.commit()
            results.append(category.id)  # read before close, while still attached
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=_resolve) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"concurrent category resolution raised: {errors}"
    assert len(results) == 2
    assert results[0] == results[1]

    all_matching = list(
        db_session.scalars(
            select(Category).where(Category.name == "Concurrent Test Category")
        )
    )
    assert len(all_matching) == 1
