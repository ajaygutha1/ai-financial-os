import io
from decimal import Decimal
from typing import Any

from ofxparse import AccountType as OfxAccountType
from ofxparse import OfxParser

from app.core.exceptions import ValidationError
from app.ingestion.connectors.base import RawAccount, RawTransaction
from app.models.account import AccountType
from app.models.transaction import ImportSource

_BANK_SUBTYPE_MAP = {
    "CHECKING": AccountType.CHECKING.value,
    "SAVINGS": AccountType.SAVINGS.value,
    "MONEYMRKT": AccountType.SAVINGS.value,
    "CREDITLINE": AccountType.CREDIT_CARD.value,
}


def _map_account_type(account: Any) -> str:
    if account.type == OfxAccountType.CreditCard:
        return AccountType.CREDIT_CARD.value
    if account.type == OfxAccountType.Investment:
        return AccountType.INVESTMENT.value
    return _BANK_SUBTYPE_MAP.get((account.account_type or "").upper(), AccountType.CHECKING.value)


class OfxConnector:
    """Parses a real OFX/QFX file (via `ofxparse`). Unlike Plaid/Coinbase/
    Robinhood, OFX has no server-side pagination concept -- it's a one-shot
    file dump -- so `fetch_transactions` ignores `cursor` and always returns
    everything in the file. This means OfxConnector is exercised through an
    upload endpoint (`POST /imports/ofx`), the same calling pattern as CSV
    import, not through the Celery sync task.
    """

    source = ImportSource.OFX

    def __init__(self, content: bytes) -> None:
        try:
            self._ofx = OfxParser.parse(io.BytesIO(content))
        except Exception as exc:
            raise ValidationError(f"Could not parse OFX/QFX file: {exc}") from exc

    def fetch_accounts(self) -> list[RawAccount]:
        accounts = []
        for account in self._ofx.accounts:
            statement = account.statement
            currency = (getattr(statement, "currency", None) or "USD").upper()
            institution = getattr(account, "institution", None)
            accounts.append(
                RawAccount(
                    external_account_id=account.account_id,
                    name=account.account_id,
                    account_type=_map_account_type(account),
                    currency=currency,
                    current_balance=getattr(statement, "balance", None) or Decimal("0"),
                    available_balance=getattr(statement, "available_balance", None),
                    institution_name=getattr(institution, "organization", None)
                    if institution
                    else None,
                )
            )
        return accounts

    def fetch_transactions(self, cursor: str | None) -> tuple[list[RawTransaction], str | None]:
        raw_transactions: list[RawTransaction] = []
        for account in self._ofx.accounts:
            statement = account.statement
            if statement is None:
                continue
            currency = (getattr(statement, "currency", None) or "USD").upper()
            for txn in statement.transactions:
                posted_at = txn.date.date() if hasattr(txn.date, "date") else txn.date
                raw_transactions.append(
                    RawTransaction(
                        external_transaction_id=txn.id or None,
                        posted_at=posted_at,
                        amount=Decimal(str(txn.amount)),
                        description=(txn.payee or txn.memo or "").strip(),
                        currency=currency,
                        raw={"memo": txn.memo, "type": txn.type, "checknum": txn.checknum},
                    )
                )
        return raw_transactions, None
