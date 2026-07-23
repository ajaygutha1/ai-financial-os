import uuid
from typing import Any

from app.ingestion.connectors.plaid.client import (
    PlaidAccountData,
    PlaidClient,
    PlaidSyncResult,
    PlaidWebhookVerificationKey,
)


class FakePlaidClient(PlaidClient):
    """Test double: pre-scripted responses instead of real network calls,
    mirroring FakeAIProvider's pattern. `accounts` and `sync_pages` are
    keyed by access_token so a test can script more than one linked item.
    `sync_pages` is a list consumed one call at a time (in call order),
    letting a test simulate multi-page catch-up across successive
    fetch_transactions calls the same way BaseStubConnector's cursor does.
    """

    def __init__(
        self,
        *,
        accounts_by_token: dict[str, list[PlaidAccountData]] | None = None,
        sync_pages_by_token: dict[str, list[PlaidSyncResult]] | None = None,
        exchange_result: tuple[str, str] | None = None,
        webhook_key: PlaidWebhookVerificationKey | None = None,
        link_token: str = "link-sandbox-fake-token",
    ) -> None:
        self.accounts_by_token = accounts_by_token or {}
        self._sync_pages_by_token = {
            token: list(pages) for token, pages in (sync_pages_by_token or {}).items()
        }
        self._exchange_result = exchange_result or (
            f"access-sandbox-{uuid.uuid4()}",
            f"item-{uuid.uuid4()}",
        )
        self._webhook_key = webhook_key
        self._link_token = link_token
        self.calls: list[dict[str, Any]] = []

    def create_link_token(self, *, user_id: str, webhook_url: str | None) -> str:
        self.calls.append(
            {"method": "create_link_token", "user_id": user_id, "webhook_url": webhook_url}
        )
        return self._link_token

    def exchange_public_token(self, public_token: str) -> tuple[str, str]:
        self.calls.append({"method": "exchange_public_token", "public_token": public_token})
        return self._exchange_result

    def get_accounts(self, access_token: str) -> list[PlaidAccountData]:
        self.calls.append({"method": "get_accounts", "access_token": access_token})
        return self.accounts_by_token.get(access_token, [])

    def sync_transactions(self, access_token: str, cursor: str | None) -> PlaidSyncResult:
        self.calls.append(
            {"method": "sync_transactions", "access_token": access_token, "cursor": cursor}
        )
        pages = self._sync_pages_by_token.get(access_token, [])
        if not pages:
            return PlaidSyncResult(next_cursor=cursor or "", has_more=False)
        return pages.pop(0)

    def get_webhook_verification_key(self, key_id: str) -> PlaidWebhookVerificationKey:
        self.calls.append({"method": "get_webhook_verification_key", "key_id": key_id})
        if self._webhook_key is None:
            raise AssertionError("FakePlaidClient.webhook_key was not scripted for this test.")
        return self._webhook_key
