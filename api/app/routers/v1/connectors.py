import json
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.plaid_webhook import verify_plaid_webhook
from app.core.security import get_current_user
from app.ingestion.connectors.plaid.client import PlaidClient
from app.ingestion.connectors.plaid.dependency import get_plaid_client
from app.jobs.tasks.sync_accounts import sync_account
from app.models.account import AccountSource
from app.models.user import User
from app.repositories.account_repository import AccountRepository
from app.repositories.connector_credential_repository import ConnectorCredentialRepository
from app.schemas.connector import (
    ExchangePublicTokenRequest,
    ExchangePublicTokenResponse,
    LinkTokenResponse,
)
from app.services.plaid_link_service import PlaidLinkService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connectors", tags=["connectors"])

# Only this one webhook_code actually matters for a /transactions/sync-based
# integration -- it's Plaid's signal that new data is ready to pull. Other
# TRANSACTIONS codes (INITIAL_UPDATE, HISTORICAL_UPDATE, DEFAULT_UPDATE) are
# holdovers from the older non-cursor API; ITEM/AUTH/etc. webhook types are
# for products this integration doesn't use yet.
_RESYNC_WEBHOOK_CODE = "SYNC_UPDATES_AVAILABLE"


@router.post("/plaid/link-token", response_model=LinkTokenResponse)
def create_plaid_link_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    plaid_client: PlaidClient = Depends(get_plaid_client),
) -> LinkTokenResponse:
    service = PlaidLinkService(db, plaid_client)
    return LinkTokenResponse(link_token=service.create_link_token(current_user.id))


@router.post("/plaid/exchange", response_model=ExchangePublicTokenResponse)
def exchange_plaid_public_token(
    payload: ExchangePublicTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    plaid_client: PlaidClient = Depends(get_plaid_client),
) -> ExchangePublicTokenResponse:
    service = PlaidLinkService(db, plaid_client)
    accounts = service.exchange_public_token(
        current_user.id,
        public_token=payload.public_token,
        institution_name=payload.institution_name,
    )
    return ExchangePublicTokenResponse(accounts=accounts)


@router.post("/plaid/webhook")
async def plaid_webhook(
    request: Request,
    db: Session = Depends(get_db),
    plaid_client: PlaidClient = Depends(get_plaid_client),
) -> dict[str, str]:
    # Plaid calls this endpoint directly -- no user session exists, so
    # authenticity comes entirely from verify_plaid_webhook's JWT check
    # rather than get_current_user. Must read the raw body for the
    # signature check *before* any JSON parsing.
    body = await request.body()
    verify_plaid_webhook(
        body=body,
        verification_header=request.headers.get("plaid-verification"),
        plaid_client=plaid_client,
    )

    payload = json.loads(body)
    if payload.get("webhook_code") != _RESYNC_WEBHOOK_CODE:
        logger.info("Ignoring Plaid webhook_code=%s", payload.get("webhook_code"))
        return {"status": "ignored"}

    item_id = payload.get("item_id")
    credential = (
        ConnectorCredentialRepository(db).get_by_provider_and_item(
            provider=AccountSource.PLAID.value, external_item_id=item_id
        )
        if item_id
        else None
    )
    if credential is None:
        logger.warning("Plaid webhook for unknown item_id=%s", item_id)
        return {"status": "ignored"}

    for account in AccountRepository(db).list_by_credential(credential.id):
        sync_account.delay(str(account.id))

    return {"status": "ok"}
