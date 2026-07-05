import pytest

from app.ingestion.connectors.coinbase_stub import CoinbaseStubConnector
from app.ingestion.connectors.plaid_stub import PlaidStubConnector
from app.ingestion.connectors.robinhood_stub import RobinhoodStubConnector
from app.ingestion.connectors.stub_base import PAGE_SIZE, TOTAL_PAGES

CONNECTOR_CLASSES = [PlaidStubConnector, CoinbaseStubConnector, RobinhoodStubConnector]


@pytest.mark.parametrize("connector_cls", CONNECTOR_CLASSES)
def test_fetch_accounts_is_deterministic(connector_cls: type) -> None:
    first = connector_cls("acct-123").fetch_accounts()
    second = connector_cls("acct-123").fetch_accounts()
    assert first == second
    assert len(first) == 1


@pytest.mark.parametrize("connector_cls", CONNECTOR_CLASSES)
def test_different_accounts_produce_different_fixtures(connector_cls: type) -> None:
    a = connector_cls("acct-aaa").fetch_accounts()
    b = connector_cls("acct-bbb").fetch_accounts()
    assert a != b


@pytest.mark.parametrize("connector_cls", CONNECTOR_CLASSES)
def test_first_page_returns_full_batch_and_cursor(connector_cls: type) -> None:
    connector = connector_cls("acct-123")
    transactions, cursor = connector.fetch_transactions(cursor=None)

    assert len(transactions) == PAGE_SIZE
    assert cursor is not None
    assert all(t.external_transaction_id for t in transactions)


@pytest.mark.parametrize("connector_cls", CONNECTOR_CLASSES)
def test_same_cursor_returns_same_batch(connector_cls: type) -> None:
    connector = connector_cls("acct-123")
    first_batch, next_cursor = connector.fetch_transactions(cursor=None)

    # A fresh connector instance (simulating a retried/re-run sync) with the
    # same cursor must reproduce the identical batch -- idempotent by design.
    replay_batch, replay_cursor = connector_cls("acct-123").fetch_transactions(cursor=None)
    assert first_batch == replay_batch
    assert next_cursor == replay_cursor


@pytest.mark.parametrize("connector_cls", CONNECTOR_CLASSES)
def test_pagination_exhausts_cleanly(connector_cls: type) -> None:
    connector = connector_cls("acct-123")
    cursor = None
    seen_ids: set[str] = set()

    for _ in range(TOTAL_PAGES):
        transactions, cursor = connector.fetch_transactions(cursor=cursor)
        assert len(transactions) == PAGE_SIZE
        seen_ids.update(
            t.external_transaction_id for t in transactions if t.external_transaction_id
        )

    assert len(seen_ids) == PAGE_SIZE * TOTAL_PAGES

    # Exhausted: further calls with the same cursor return nothing new, and
    # the cursor itself doesn't change (mirrors Plaid's has_more=False).
    empty_batch, same_cursor = connector.fetch_transactions(cursor=cursor)
    assert empty_batch == []
    assert same_cursor == cursor


def test_coinbase_transactions_carry_asset_metadata() -> None:
    transactions, _ = CoinbaseStubConnector("acct-crypto").fetch_transactions(cursor=None)
    assert all("asset" in t.raw for t in transactions)
    assert all(t.raw["asset"] in {"BTC", "ETH", "SOL", "USDC"} for t in transactions)


def test_robinhood_transactions_carry_ticker_metadata() -> None:
    transactions, _ = RobinhoodStubConnector("acct-brokerage").fetch_transactions(cursor=None)
    assert all("ticker" in t.raw for t in transactions)
