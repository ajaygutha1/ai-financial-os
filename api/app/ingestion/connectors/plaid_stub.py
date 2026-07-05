import random
from datetime import date
from decimal import Decimal

from app.ingestion.connectors.base import RawAccount, RawTransaction
from app.ingestion.connectors.stub_base import BaseStubConnector, signed_amount
from app.models.account import AccountType
from app.models.transaction import ImportSource

_MERCHANTS = [
    "Whole Foods Market",
    "Shell Gas Station",
    "Trader Joe's",
    "Netflix",
    "Chipotle",
    "Target",
    "Amazon.com",
]


class PlaidStubConnector(BaseStubConnector):
    """Deterministic, Plaid-sandbox-shaped fake data for a generic bank
    account -- swapping this for a real Plaid connector in Milestone 9 is a
    new file implementing the same `Connector` protocol, not a redesign.
    """

    source = ImportSource.PLAID
    cursor_prefix = "plaid"

    def fetch_accounts(self) -> list[RawAccount]:
        rng = random.Random(self._seed)
        return [
            RawAccount(
                external_account_id=self.external_account_id,
                name="Plaid Checking",
                account_type=AccountType.CHECKING.value,
                currency="USD",
                current_balance=Decimal(str(round(rng.uniform(500, 8000), 2))),
                institution_name="Plaid Sandbox Bank",
            )
        ]

    def _generate_transaction(
        self, rng: random.Random, page: int, index: int, posted_at: date
    ) -> RawTransaction:
        merchant = rng.choice(_MERCHANTS)
        amount = signed_amount(rng, low="4", high="180")
        return RawTransaction(
            external_transaction_id=self._external_id(page, index),
            posted_at=posted_at,
            amount=amount,
            description=merchant,
            merchant_raw=merchant,
            currency="USD",
            raw={"source": "plaid_stub"},
        )
