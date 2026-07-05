import random
from datetime import date
from decimal import Decimal

from app.ingestion.connectors.base import RawAccount, RawTransaction
from app.ingestion.connectors.stub_base import BaseStubConnector
from app.models.account import AccountType
from app.models.transaction import ImportSource

_TICKERS = ["AAPL", "TSLA", "VOO", "NVDA", "MSFT"]


class RobinhoodStubConnector(BaseStubConnector):
    """Deterministic, Robinhood-shaped fake data -- equity buys/sells and
    dividends rather than bank-style purchases. Swapping for a real
    Robinhood connector in Milestone 9 is a new file implementing the same
    `Connector` protocol.
    """

    source = ImportSource.ROBINHOOD
    cursor_prefix = "robinhood"

    def fetch_accounts(self) -> list[RawAccount]:
        rng = random.Random(self._seed)
        return [
            RawAccount(
                external_account_id=self.external_account_id,
                name="Robinhood Brokerage",
                account_type=AccountType.INVESTMENT.value,
                currency="USD",
                current_balance=Decimal(str(round(rng.uniform(1000, 50000), 2))),
                institution_name="Robinhood",
            )
        ]

    def _generate_transaction(
        self, rng: random.Random, page: int, index: int, posted_at: date
    ) -> RawTransaction:
        ticker = rng.choice(_TICKERS)
        roll = rng.random()

        if roll < 0.1:
            amount = Decimal(str(round(rng.uniform(1, 50), 2)))
            description = f"Dividend: {ticker}"
            side = "dividend"
        else:
            is_buy = roll < 0.55
            shares = rng.randint(1, 20)
            amount = Decimal(str(round(rng.uniform(50, 3000), 2)))
            description = f"{'Bought' if is_buy else 'Sold'} {shares} shares of {ticker}"
            side = "buy" if is_buy else "sell"
            amount = -amount if is_buy else amount

        return RawTransaction(
            external_transaction_id=self._external_id(page, index),
            posted_at=posted_at,
            amount=amount,
            description=description,
            merchant_raw=f"Robinhood {ticker}",
            currency="USD",
            raw={"source": "robinhood_stub", "ticker": ticker, "side": side},
        )
