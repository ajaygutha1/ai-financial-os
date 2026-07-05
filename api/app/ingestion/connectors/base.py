from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, ClassVar, Protocol

from app.models.transaction import ImportSource


@dataclass(frozen=True)
class RawAccount:
    external_account_id: str
    name: str
    account_type: str
    currency: str
    current_balance: Decimal
    available_balance: Decimal | None = None
    mask: str | None = None
    institution_name: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawTransaction:
    external_transaction_id: str | None
    posted_at: date
    amount: Decimal  # already sign-normalized by the connector: negative = outflow
    description: str
    currency: str = "USD"
    merchant_raw: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class Connector(Protocol):
    """Every ingestion source (OFX, Plaid, Coinbase, Robinhood) implements this
    identically. The `cursor` shape mirrors real Plaid's `/transactions/sync`
    API deliberately, so Milestone 9's swap from stub to real Plaid is a new
    file implementing this same protocol, not a redesign.
    """

    source: ClassVar[ImportSource]

    def fetch_accounts(self) -> list[RawAccount]: ...

    def fetch_transactions(self, cursor: str | None) -> tuple[list[RawTransaction], str | None]: ...
