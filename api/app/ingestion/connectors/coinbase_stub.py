import random
from datetime import date
from decimal import Decimal

from app.ingestion.connectors.base import RawAccount, RawTransaction
from app.ingestion.connectors.stub_base import BaseStubConnector
from app.models.account import AccountType
from app.models.transaction import ImportSource

_ASSETS = ["BTC", "ETH", "SOL", "USDC"]


class CoinbaseStubConnector(BaseStubConnector):
    """Deterministic, Coinbase-shaped fake data -- crypto buy/sell activity
    rather than bank-style purchases. Swapping for a real Coinbase connector
    in Milestone 9 is a new file implementing the same `Connector` protocol.
    """

    source = ImportSource.COINBASE
    cursor_prefix = "coinbase"

    def fetch_accounts(self) -> list[RawAccount]:
        rng = random.Random(self._seed)
        return [
            RawAccount(
                external_account_id=self.external_account_id,
                name="Coinbase Wallet",
                account_type=AccountType.CRYPTO.value,
                currency="USD",
                current_balance=Decimal(str(round(rng.uniform(200, 15000), 2))),
                institution_name="Coinbase",
            )
        ]

    def _generate_transaction(
        self, rng: random.Random, page: int, index: int, posted_at: date
    ) -> RawTransaction:
        asset = rng.choice(_ASSETS)
        is_buy = rng.random() < 0.6
        usd_amount = Decimal(str(round(rng.uniform(20, 2000), 2)))
        quantity = round(rng.uniform(0.001, 2.5), 6)
        description = f"{'Bought' if is_buy else 'Sold'} {quantity} {asset}"
        return RawTransaction(
            external_transaction_id=self._external_id(page, index),
            posted_at=posted_at,
            amount=-usd_amount if is_buy else usd_amount,
            description=description,
            merchant_raw=f"Coinbase {asset}",
            currency="USD",
            raw={
                "source": "coinbase_stub",
                "asset": asset,
                "quantity": str(quantity),
                "side": "buy" if is_buy else "sell",
            },
        )
