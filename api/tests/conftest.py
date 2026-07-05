import os

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://finos:finos_dev_password@localhost:5432/finos_test"
)
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["JWT_SECRET"] = "test-secret-not-for-production-use-only-32bytes-min"
os.environ["ENVIRONMENT"] = "test"

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registers all models on Base.metadata)
from alembic import command
from app.core.config import get_settings
from app.core.db import Base, get_db
from app.main import app as fastapi_app
from app.models.account import Account, AccountType
from app.models.user import User

API_DIR = Path(__file__).parent.parent


def _alembic_config() -> Config:
    # env.py resolves the DB URL itself via get_settings().database_url
    # (already pointed at finos_test by the env vars set above), so nothing
    # needs to be set here beyond locating alembic.ini.
    return Config(str(API_DIR / "alembic.ini"))


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    # Real Alembic migrations, not Base.metadata.create_all(): migration 0002
    # adds a raw SQL trigger/function (audit_log immutability) and a
    # procedural hash-chain backfill that create_all can't produce, and this
    # doubles as a standing check that `alembic upgrade head` actually works
    # every time the test suite runs.
    settings = get_settings()
    eng = create_engine(settings.database_url)

    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, "head")

    yield eng

    command.downgrade(alembic_cfg, "base")
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
        # audit_log's immutability trigger (Milestone 2) rejects UPDATE/DELETE
        # unconditionally -- including the implicit UPDATE Postgres issues for
        # audit_log.user_id's ON DELETE SET NULL action when a referenced
        # `users` row is deleted below. Disabling triggers for this cleanup
        # transaction is a deliberate, explicit escape hatch available only to
        # the table owner (superuser-equivalent maintenance access) -- normal
        # application code never does this, so the production guarantee holds.
        connection.execute(text("ALTER TABLE audit_log DISABLE TRIGGER ALL"))
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
        connection.execute(text("ALTER TABLE audit_log ENABLE TRIGGER ALL"))


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
