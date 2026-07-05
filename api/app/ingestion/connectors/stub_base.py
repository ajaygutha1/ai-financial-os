import hashlib
import random
from abc import ABC, abstractmethod
from datetime import date, timedelta
from decimal import Decimal
from typing import ClassVar

from app.ingestion.connectors.base import RawAccount, RawTransaction
from app.models.transaction import ImportSource

PAGE_SIZE = 10
TOTAL_PAGES = 3  # fixed, deterministic history depth for every stub account


class BaseStubConnector(ABC):
    """Shared pagination/determinism mechanics for stubbed connectors
    (Plaid, Coinbase, Robinhood). Cursor semantics deliberately mirror real
    Plaid's `/transactions/sync`: a cursor encodes a page index; repeated
    calls with the *same* cursor return the *same* batch (idempotent); once
    exhausted, calling with the last-returned cursor again yields an empty
    page and the same cursor back (mirrors Plaid's `has_more=False`).

    Each account's fake data is seeded from its external account id, so the
    same account always produces the same fixture -- realistic-looking but
    fully reproducible, which is what makes this testable without a live
    third-party sandbox.
    """

    source: ClassVar[ImportSource]
    cursor_prefix: str

    def __init__(self, external_account_id: str) -> None:
        self.external_account_id = external_account_id
        self._seed = int.from_bytes(
            hashlib.sha256(external_account_id.encode()).digest()[:8], "big"
        )

    def fetch_transactions(self, cursor: str | None) -> tuple[list[RawTransaction], str | None]:
        page = self._parse_cursor(cursor)
        if page >= TOTAL_PAGES:
            return [], cursor

        rng = random.Random(self._seed + page)
        base_date = date.today() - timedelta(days=(TOTAL_PAGES - page) * PAGE_SIZE)
        transactions = [
            self._generate_transaction(rng, page, index, base_date + timedelta(days=index))
            for index in range(PAGE_SIZE)
        ]
        return transactions, self._make_cursor(page + 1)

    def _parse_cursor(self, cursor: str | None) -> int:
        if cursor is None:
            return 0
        _, _, page_str = cursor.partition(":")
        return int(page_str) if page_str.isdigit() else 0

    def _make_cursor(self, page: int) -> str:
        return f"{self.cursor_prefix}:{page}"

    @abstractmethod
    def fetch_accounts(self) -> list[RawAccount]: ...

    @abstractmethod
    def _generate_transaction(
        self, rng: random.Random, page: int, index: int, posted_at: date
    ) -> RawTransaction: ...

    def _external_id(self, page: int, index: int) -> str:
        return f"{self.cursor_prefix}-{self.external_account_id}-{page}-{index}"


def signed_amount(
    rng: random.Random, *, low: str, high: str, outflow_probability: float = 0.8
) -> Decimal:
    """A realistic-looking amount, negative (outflow) most of the time."""
    magnitude = Decimal(str(round(rng.uniform(float(low), float(high)), 2)))
    return -magnitude if rng.random() < outflow_probability else magnitude
