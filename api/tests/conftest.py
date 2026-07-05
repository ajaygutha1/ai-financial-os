import os

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://finos:finos_dev_password@localhost:5432/finos_test"
)
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["JWT_SECRET"] = "test-secret-not-for-production-use-only-32bytes-min"
os.environ["ENVIRONMENT"] = "test"

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registers all models on Base.metadata)
from app.core.config import get_settings
from app.core.db import Base, get_db
from app.main import app as fastapi_app
from app.models.account import Account, AccountType
from app.models.user import User


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    settings = get_settings()
    eng = create_engine(settings.database_url)
    eng.connect().execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto")).close()
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Generator[Session, None, None]:
    # A plain session per test rather than a SAVEPOINT-nested one: the service
    # layer calls `db.commit()` internally, which would prematurely end a
    # wrapping transaction. Deleting all rows after each test keeps isolation
    # without fighting that.
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    yield session

    session.close()
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session: Session) -> User:
    from app.core.security import hash_password

    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password=hash_password("correct-horse-battery"),
        full_name="Test User",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def auth_headers(client: TestClient, test_user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "correct-horse-battery"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_account(db_session: Session, test_user: User) -> Account:
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Checking",
        account_type=AccountType.CHECKING.value,
        current_balance=1000,
    )
    db_session.add(account)
    db_session.commit()
    return account
