import logging
from typing import ClassVar

from app.ingestion.connectors.base import RawAccount, RawTransaction
from app.ingestion.connectors.plaid.client import PlaidClient, PlaidTransactionData
from app.models.transaction import ImportSource

logger = logging.getLogger(__name__)


class PlaidConnector:
    """The real Plaid connector -- implements the same `Connector` protocol
    as every stub, per the Milestone 2 design note that this swap would be
    "a new file implementing this same protocol, not a redesign."

    Plaid's `/transactions/sync` operates at the Item level (one access
    token can back several of our `Account` rows), but `SyncService` syncs
    exactly one `Account` per call -- so this connector is constructed per
    `(access_token, external_account_id)` pair and filters the Item-wide
    response down to just the one account being synced. Each linked
    account therefore re-fetches the same delta window from Plaid
    independently; redundant but harmless (Plaid's sync cursor is
    stateless/idempotent from the caller's side), and it means zero changes
    to the existing per-account sync task/SyncJob model.
    """

    source: ClassVar[ImportSource] = ImportSource.PLAID

    def __init__(self, client: PlaidClient, *, access_token: str, external_account_id: str) -> None:
        self._client = client
        self._access_token = access_token
        self._external_account_id = external_account_id

    def fetch_accounts(self) -> list[RawAccount]:
        accounts = self._client.get_accounts(self._access_token)
        return [
            RawAccount(
                external_account_id=a.external_account_id,
                name=a.name,
                account_type=a.account_type,
                currency=a.currency,
                current_balance=a.current_balance,
                available_balance=a.available_balance,
                mask=a.mask,
                raw={"account_subtype": a.account_subtype},
            )
            for a in accounts
            if a.external_account_id == self._external_account_id
        ]

    def fetch_transactions(self, cursor: str | None) -> tuple[list[RawTransaction], str | None]:
        result = self._client.sync_transactions(self._access_token, cursor)

        if result.removed_transaction_ids:
            # The shared normalization pipeline (Milestone 2) has no
            # deletion path -- a transaction that Plaid reports as removed
            # (typically a pending entry superseded by its posted version)
            # is deliberately left in place rather than silently dropped.
            # Documented limitation, not a bug: retrofitting deletion
            # semantics into the shared pipeline is bigger than this
            # milestone's "additive, not a rewrite" scope.
            logger.warning(
                "Plaid reported %d removed transaction(s) for account %s -- "
                "not deleted locally (no deletion path in the sync pipeline).",
                len(result.removed_transaction_ids),
                self._external_account_id,
            )

        relevant = [
            txn
            for txn in (*result.added, *result.modified)
            if txn.plaid_account_id == self._external_account_id
        ]
        return [self._to_raw_transaction(txn) for txn in relevant], result.next_cursor

    def _to_raw_transaction(self, txn: PlaidTransactionData) -> RawTransaction:
        return RawTransaction(
            external_transaction_id=txn.plaid_transaction_id,
            posted_at=txn.posted_at,
            # Sign-flip: Plaid's convention is positive = outflow, ours is
            # negative = outflow (see PlaidTransactionData's docstring).
            amount=-txn.amount,
            description=txn.name,
            currency=txn.currency,
            merchant_raw=txn.merchant_name,
            raw={"source": "plaid", "pending": txn.pending},
        )
