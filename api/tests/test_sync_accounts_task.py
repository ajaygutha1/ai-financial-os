import uuid

import pytest
from sqlalchemy.orm import Session

from app.ingestion.connectors.coinbase_stub import CoinbaseStubConnector
from app.ingestion.connectors.plaid_stub import PlaidStubConnector
from app.ingestion.connectors.robinhood_stub import RobinhoodStubConnector
from app.jobs.tasks.sync_accounts import build_connector_for_account
from app.models.account import Account, AccountType
from app.models.user import User


def _account(
    db_session: Session, test_user: User, *, source: str, external_account_id: str | None
) -> Account:
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Linked Account",
        account_type=AccountType.CHECKING.value,
        current_balance=0,
        source=source,
        external_account_id=external_account_id,
    )
    db_session.add(account)
    db_session.commit()
    return account


@pytest.mark.parametrize(
    "source,expected_cls",
    [
        ("plaid", PlaidStubConnector),
        ("coinbase", CoinbaseStubConnector),
        ("robinhood", RobinhoodStubConnector),
    ],
)
def test_build_connector_for_account_returns_matching_stub(
    db_session: Session, test_user: User, source: str, expected_cls: type
) -> None:
    account = _account(db_session, test_user, source=source, external_account_id="ext-1")
    connector = build_connector_for_account(account)
    assert isinstance(connector, expected_cls)


def test_build_connector_for_unsupported_source_raises(
    db_session: Session, test_user: User
) -> None:
    account = _account(db_session, test_user, source="manual", external_account_id="ext-1")
    with pytest.raises(ValueError, match="No connector available"):
        build_connector_for_account(account)


def test_build_connector_without_external_id_raises(db_session: Session, test_user: User) -> None:
    account = _account(db_session, test_user, source="plaid", external_account_id=None)
    with pytest.raises(ValueError, match="external_account_id"):
        build_connector_for_account(account)
