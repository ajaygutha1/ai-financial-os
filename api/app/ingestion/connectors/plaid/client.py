from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class PlaidAccountData:
    external_account_id: str
    name: str
    account_type: str  # already mapped to our AccountType, see _map_account_type
    account_subtype: str | None
    currency: str
    current_balance: Decimal
    available_balance: Decimal | None
    mask: str | None


@dataclass(frozen=True)
class PlaidTransactionData:
    plaid_transaction_id: str
    plaid_account_id: str
    posted_at: date
    # Plaid convention: positive = money left the account (outflow),
    # negative = inflow -- the *opposite* of this codebase's RawTransaction
    # convention. Left un-flipped here; PlaidConnector does the flip, so
    # this dataclass stays an honest mirror of what Plaid actually returns.
    amount: Decimal
    name: str
    merchant_name: str | None
    currency: str
    pending: bool


@dataclass(frozen=True)
class PlaidSyncResult:
    added: list[PlaidTransactionData] = field(default_factory=list)
    modified: list[PlaidTransactionData] = field(default_factory=list)
    removed_transaction_ids: list[str] = field(default_factory=list)
    next_cursor: str = ""
    has_more: bool = False


@dataclass(frozen=True)
class PlaidWebhookVerificationKey:
    """A JWK as returned by /webhook_verification_key/get, in the shape
    `jwt.algorithms.ECAlgorithm.from_jwk` expects (json-serializable dict)."""

    key_id: str
    jwk: dict[str, Any]


class PlaidClient(ABC):
    """Every Plaid API call goes through this interface -- only
    real_client.py may `import plaid`. Mirrors the AIProvider adapter
    pattern (app/ai/provider/base.py): one abstract interface, a real
    implementation, and a fully scriptable fake for tests."""

    @abstractmethod
    def create_link_token(self, *, user_id: str, webhook_url: str | None) -> str: ...

    @abstractmethod
    def exchange_public_token(self, public_token: str) -> tuple[str, str]:
        """Returns (access_token, item_id)."""
        ...

    @abstractmethod
    def get_accounts(self, access_token: str) -> list[PlaidAccountData]: ...

    @abstractmethod
    def sync_transactions(self, access_token: str, cursor: str | None) -> PlaidSyncResult: ...

    @abstractmethod
    def get_webhook_verification_key(self, key_id: str) -> PlaidWebhookVerificationKey: ...
