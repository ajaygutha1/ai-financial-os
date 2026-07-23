from decimal import Decimal
from typing import Any, cast

import plaid
from plaid.api import plaid_api
from plaid.exceptions import ApiException
from plaid.model.account_base import AccountBase
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transaction import Transaction
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.webhook_verification_key_get_request import WebhookVerificationKeyGetRequest

from app.core.exceptions import ServiceUnavailableError
from app.ingestion.connectors.plaid.client import (
    PlaidAccountData,
    PlaidClient,
    PlaidSyncResult,
    PlaidTransactionData,
    PlaidWebhookVerificationKey,
)
from app.models.account import AccountType

_ENVIRONMENTS = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}

# Deliberately not exhaustive of every Plaid subtype (there are ~70) --
# covers the common consumer cases; anything unmapped falls through to
# OTHER rather than raising, since an unrecognized subtype shouldn't block
# a sync.
_RETIREMENT_SUBTYPES = {
    "401a",
    "401k",
    "403b",
    "457b",
    "529",
    "ira",
    "roth",
    "roth 401k",
    "roth 403b",
    "roth 457b",
    "sep ira",
    "simple ira",
    "pension",
    "retirement",
    "thrift savings plan",
}


def _map_account_type(plaid_type: str, plaid_subtype: str | None) -> str:
    if plaid_subtype == "checking":
        return AccountType.CHECKING.value
    if plaid_subtype == "savings":
        return AccountType.SAVINGS.value
    if plaid_subtype == "credit card":
        return AccountType.CREDIT_CARD.value
    if plaid_subtype == "mortgage":
        return AccountType.MORTGAGE.value
    if plaid_subtype in _RETIREMENT_SUBTYPES:
        return AccountType.RETIREMENT.value
    if plaid_type == "loan":
        return AccountType.LOAN.value
    if plaid_type in ("investment", "brokerage"):
        return AccountType.INVESTMENT.value
    if plaid_type == "credit":
        return AccountType.CREDIT_CARD.value
    if plaid_type == "depository":
        return AccountType.CHECKING.value
    return AccountType.OTHER.value


def _map_account(account: AccountBase) -> PlaidAccountData:
    balances = account.balances
    plaid_type = str(account.type.value) if account.type else "other"
    plaid_subtype = str(account.subtype.value) if account.subtype else None
    return PlaidAccountData(
        external_account_id=account.account_id,
        name=account.official_name or account.name,
        account_type=_map_account_type(plaid_type, plaid_subtype),
        account_subtype=plaid_subtype,
        currency=balances.iso_currency_code or "USD",
        current_balance=Decimal(str(balances.current))
        if balances.current is not None
        else Decimal("0"),
        available_balance=(
            Decimal(str(balances.available)) if balances.available is not None else None
        ),
        mask=account.mask,
    )


def _map_transaction(txn: Transaction) -> PlaidTransactionData:
    return PlaidTransactionData(
        plaid_transaction_id=txn.transaction_id,
        plaid_account_id=txn.account_id,
        posted_at=txn.date,
        amount=Decimal(str(txn.amount)),
        name=txn.name,
        merchant_name=txn.merchant_name,
        currency=txn.iso_currency_code or "USD",
        pending=txn.pending,
    )


class RealPlaidClient(PlaidClient):
    """The only module that may `import plaid` -- everything else talks to
    the `PlaidClient` interface. Sync client, matching this codebase's sync
    SQLAlchemy/FastAPI style (same rationale as AnthropicProvider)."""

    def __init__(self, *, client_id: str, secret: str, environment: str) -> None:
        if environment not in _ENVIRONMENTS:
            raise ValueError(
                f"Unsupported plaid_env {environment!r} -- must be one of {sorted(_ENVIRONMENTS)}."
            )
        self._client_id = client_id
        self._secret = secret
        configuration = plaid.Configuration(host=_ENVIRONMENTS[environment])
        self._api = plaid_api.PlaidApi(plaid.ApiClient(configuration))

    def _auth(self) -> dict[str, str]:
        return {"client_id": self._client_id, "secret": self._secret}

    def create_link_token(self, *, user_id: str, webhook_url: str | None) -> str:
        kwargs: dict[str, Any] = {
            **self._auth(),
            "client_name": "AI Financial OS",
            "language": "en",
            "country_codes": [CountryCode("US")],
            "user": LinkTokenCreateRequestUser(client_user_id=user_id),
            "products": [Products("transactions")],
        }
        if webhook_url:
            kwargs["webhook"] = webhook_url
        try:
            response = self._api.link_token_create(LinkTokenCreateRequest(**kwargs))
        except ApiException as exc:
            raise ServiceUnavailableError("Plaid link token creation failed.") from exc
        return cast(str, response.link_token)

    def exchange_public_token(self, public_token: str) -> tuple[str, str]:
        request = ItemPublicTokenExchangeRequest(**self._auth(), public_token=public_token)
        try:
            response = self._api.item_public_token_exchange(request)
        except ApiException as exc:
            raise ServiceUnavailableError("Plaid public token exchange failed.") from exc
        return response.access_token, response.item_id

    def get_accounts(self, access_token: str) -> list[PlaidAccountData]:
        request = AccountsGetRequest(**self._auth(), access_token=access_token)
        try:
            response = self._api.accounts_get(request)
        except ApiException as exc:
            raise ServiceUnavailableError("Plaid accounts fetch failed.") from exc
        return [_map_account(a) for a in response.accounts]

    def sync_transactions(self, access_token: str, cursor: str | None) -> PlaidSyncResult:
        kwargs: dict[str, Any] = {**self._auth(), "access_token": access_token}
        if cursor:
            kwargs["cursor"] = cursor
        try:
            response = self._api.transactions_sync(TransactionsSyncRequest(**kwargs))
        except ApiException as exc:
            raise ServiceUnavailableError("Plaid transactions sync failed.") from exc
        return PlaidSyncResult(
            added=[_map_transaction(t) for t in response.added],
            modified=[_map_transaction(t) for t in response.modified],
            removed_transaction_ids=[r.transaction_id for r in response.removed],
            next_cursor=response.next_cursor,
            has_more=response.has_more,
        )

    def get_webhook_verification_key(self, key_id: str) -> PlaidWebhookVerificationKey:
        request = WebhookVerificationKeyGetRequest(**self._auth(), key_id=key_id)
        try:
            response = self._api.webhook_verification_key_get(request)
        except ApiException as exc:
            raise ServiceUnavailableError("Plaid webhook key fetch failed.") from exc
        key = response.key
        jwk = {
            "kty": key.kty,
            "crv": key.crv,
            "kid": key.kid,
            "use": key.use,
            "alg": key.alg,
            "x": key.x,
            "y": key.y,
        }
        return PlaidWebhookVerificationKey(key_id=key.kid, jwk=jwk)
