import uuid

import pytest
from sqlalchemy.orm import Session

from app.ingestion.connectors.coinbase_stub import CoinbaseStubConnector
from app.ingestion.connectors.plaid_connector import PlaidConnector
from app.ingestion.connectors.plaid_stub import PlaidStubConnector
from app.ingestion.connectors.robinhood_stub import RobinhoodStubConnector
from app.jobs.tasks import sync_accounts as sync_accounts_module
from app.jobs.tasks.sync_accounts import build_connector_for_account
from app.models.account import Account, AccountType
from app.models.connector_credential import ConnectorCredential
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
    connector = build_connector_for_account(account, db_session)
    assert isinstance(connector, expected_cls)


def test_build_connector_for_unsupported_source_raises(
    db_session: Session, test_user: User
) -> None:
    account = _account(db_session, test_user, source="manual", external_account_id="ext-1")
    with pytest.raises(ValueError, match="No connector available"):
        build_connector_for_account(account, db_session)


def test_build_connector_without_external_id_raises(db_session: Session, test_user: User) -> None:
    account = _account(db_session, test_user, source="plaid", external_account_id=None)
    with pytest.raises(ValueError, match="external_account_id"):
        build_connector_for_account(account, db_session)


def test_build_connector_uses_real_plaid_connector_when_credential_linked(
    db_session: Session, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ingestion.connectors.plaid.fake_client import FakePlaidClient

    fake_client = FakePlaidClient()
    monkeypatch.setattr(sync_accounts_module, "get_plaid_client", lambda: fake_client)

    credential = ConnectorCredential(
        user_id=test_user.id,
        provider="plaid",
        external_item_id="item-1",
        access_token_enc="access-sandbox-real-1",
    )
    db_session.add(credential)
    db_session.commit()

    account = _account(db_session, test_user, source="plaid", external_account_id="ext-1")
    account.connector_credential_id = credential.id
    db_session.commit()

    connector = build_connector_for_account(account, db_session)

    assert isinstance(connector, PlaidConnector)


def test_build_connector_falls_back_to_stub_for_plaid_account_without_credential(
    db_session: Session, test_user: User
) -> None:
    account = _account(db_session, test_user, source="plaid", external_account_id="ext-1")
    connector = build_connector_for_account(account, db_session)
    assert isinstance(connector, PlaidStubConnector)


def test_build_connector_raises_when_linked_credential_has_no_token(
    db_session: Session, test_user: User
) -> None:
    # A credential row can exist with no usable token (e.g. revoked) --
    # the FK constraint means a *missing* row can't happen while linked,
    # so this is the realistic "unusable credential" case to guard against.
    credential = ConnectorCredential(
        user_id=test_user.id,
        provider="plaid",
        external_item_id="item-revoked",
        access_token_enc=None,
    )
    db_session.add(credential)
    db_session.commit()

    account = _account(db_session, test_user, source="plaid", external_account_id="ext-1")
    account.connector_credential_id = credential.id
    db_session.commit()

    with pytest.raises(ValueError, match="no usable Plaid credential"):
        build_connector_for_account(account, db_session)
