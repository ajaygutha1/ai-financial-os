from datetime import date
from decimal import Decimal

from app.ingestion.connectors.plaid.client import (
    PlaidAccountData,
    PlaidSyncResult,
    PlaidTransactionData,
)
from app.ingestion.connectors.plaid.fake_client import FakePlaidClient
from app.ingestion.connectors.plaid_connector import PlaidConnector
from app.models.account import AccountType

ACCESS_TOKEN = "access-sandbox-abc123"
OUR_ACCOUNT_ID = "plaid-account-1"
OTHER_ACCOUNT_ID = "plaid-account-2"


def _account(external_account_id: str) -> PlaidAccountData:
    return PlaidAccountData(
        external_account_id=external_account_id,
        name="Plaid Checking",
        account_type=AccountType.CHECKING.value,
        account_subtype="checking",
        currency="USD",
        current_balance=Decimal("1234.56"),
        available_balance=Decimal("1200.00"),
        mask="0000",
    )


def _transaction(*, account_id: str, txn_id: str, amount: Decimal) -> PlaidTransactionData:
    return PlaidTransactionData(
        plaid_transaction_id=txn_id,
        plaid_account_id=account_id,
        posted_at=date(2026, 6, 1),
        amount=amount,
        name="Whole Foods",
        merchant_name="Whole Foods Market",
        currency="USD",
        pending=False,
    )


def test_fetch_accounts_filters_to_the_one_account_this_connector_targets() -> None:
    client = FakePlaidClient(
        accounts_by_token={ACCESS_TOKEN: [_account(OUR_ACCOUNT_ID), _account(OTHER_ACCOUNT_ID)]}
    )
    connector = PlaidConnector(
        client, access_token=ACCESS_TOKEN, external_account_id=OUR_ACCOUNT_ID
    )

    accounts = connector.fetch_accounts()

    assert len(accounts) == 1
    assert accounts[0].external_account_id == OUR_ACCOUNT_ID
    assert accounts[0].current_balance == Decimal("1234.56")


def test_fetch_transactions_filters_by_account_and_flips_the_sign() -> None:
    sync_result = PlaidSyncResult(
        added=[
            _transaction(account_id=OUR_ACCOUNT_ID, txn_id="t1", amount=Decimal("42.50")),
            _transaction(account_id=OTHER_ACCOUNT_ID, txn_id="t2", amount=Decimal("10.00")),
        ],
        next_cursor="cursor-1",
        has_more=False,
    )
    client = FakePlaidClient(sync_pages_by_token={ACCESS_TOKEN: [sync_result]})
    connector = PlaidConnector(
        client, access_token=ACCESS_TOKEN, external_account_id=OUR_ACCOUNT_ID
    )

    transactions, next_cursor = connector.fetch_transactions(cursor=None)

    assert len(transactions) == 1
    assert transactions[0].external_transaction_id == "t1"
    # Plaid: positive = outflow. Ours: negative = outflow.
    assert transactions[0].amount == Decimal("-42.50")
    assert next_cursor == "cursor-1"


def test_fetch_transactions_includes_modified_alongside_added() -> None:
    sync_result = PlaidSyncResult(
        added=[_transaction(account_id=OUR_ACCOUNT_ID, txn_id="t1", amount=Decimal("5.00"))],
        modified=[_transaction(account_id=OUR_ACCOUNT_ID, txn_id="t2", amount=Decimal("6.00"))],
        next_cursor="cursor-2",
    )
    client = FakePlaidClient(sync_pages_by_token={ACCESS_TOKEN: [sync_result]})
    connector = PlaidConnector(
        client, access_token=ACCESS_TOKEN, external_account_id=OUR_ACCOUNT_ID
    )

    transactions, _ = connector.fetch_transactions(cursor=None)

    ids = {t.external_transaction_id for t in transactions}
    assert ids == {"t1", "t2"}


def test_fetch_transactions_does_not_raise_on_removed_entries() -> None:
    sync_result = PlaidSyncResult(removed_transaction_ids=["gone-1"], next_cursor="cursor-3")
    client = FakePlaidClient(sync_pages_by_token={ACCESS_TOKEN: [sync_result]})
    connector = PlaidConnector(
        client, access_token=ACCESS_TOKEN, external_account_id=OUR_ACCOUNT_ID
    )

    transactions, next_cursor = connector.fetch_transactions(cursor=None)

    assert transactions == []
    assert next_cursor == "cursor-3"


def test_fetch_transactions_passes_the_cursor_through_to_the_client() -> None:
    client = FakePlaidClient(
        sync_pages_by_token={ACCESS_TOKEN: [PlaidSyncResult(next_cursor="cursor-4")]}
    )
    connector = PlaidConnector(
        client, access_token=ACCESS_TOKEN, external_account_id=OUR_ACCOUNT_ID
    )

    connector.fetch_transactions(cursor="cursor-3")

    sync_call = next(c for c in client.calls if c["method"] == "sync_transactions")
    assert sync_call["cursor"] == "cursor-3"
