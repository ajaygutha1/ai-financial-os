import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.connectors.plaid.client import PlaidClient
from app.jobs.tasks.sync_accounts import sync_account
from app.models.account import Account, AccountSource
from app.models.connector_credential import ConnectorCredentialStatus
from app.repositories.account_repository import AccountRepository
from app.repositories.connector_credential_repository import ConnectorCredentialRepository


class PlaidLinkService:
    """Orchestrates the Plaid Link flow: mint a Link token, and on success
    exchange the public token for a real access token, persist it (Milestone
    8's EncryptedString handles encryption at rest transparently), and
    create/refresh one `Account` row per account Plaid returns for that
    Item."""

    def __init__(self, db: Session, plaid_client: PlaidClient) -> None:
        self.db = db
        self.plaid_client = plaid_client
        self.credentials = ConnectorCredentialRepository(db)
        self.accounts = AccountRepository(db)

    def create_link_token(self, user_id: uuid.UUID) -> str:
        settings = get_settings()
        webhook_url = f"{settings.oauth_redirect_base_url}/api/v1/connectors/plaid/webhook"
        return self.plaid_client.create_link_token(user_id=str(user_id), webhook_url=webhook_url)

    def exchange_public_token(
        self, user_id: uuid.UUID, *, public_token: str, institution_name: str | None
    ) -> list[Account]:
        access_token, item_id = self.plaid_client.exchange_public_token(public_token)

        credential = self.credentials.get_by_user_provider_item(
            user_id=user_id, provider=AccountSource.PLAID.value, external_item_id=item_id
        )
        if credential is None:
            credential = self.credentials.create(
                user_id=user_id,
                provider=AccountSource.PLAID.value,
                external_item_id=item_id,
                institution_name=institution_name,
                access_token_enc=access_token,
            )
        else:
            # Re-linking the same Item (e.g. Plaid Link's update-mode flow
            # after an expired login) -- refresh the token in place rather
            # than erroring or creating a duplicate credential row.
            credential.access_token_enc = access_token
            credential.institution_name = institution_name or credential.institution_name
            credential.status = ConnectorCredentialStatus.ACTIVE.value
        self.db.flush()

        plaid_accounts = self.plaid_client.get_accounts(access_token)
        linked_accounts: list[Account] = []
        for plaid_account in plaid_accounts:
            existing = self.accounts.get_by_credential_and_external_id(
                connector_credential_id=credential.id,
                external_account_id=plaid_account.external_account_id,
            )
            if existing is not None:
                existing.current_balance = plaid_account.current_balance
                existing.available_balance = plaid_account.available_balance
                linked_accounts.append(existing)
                continue

            linked_accounts.append(
                self.accounts.create(
                    user_id=user_id,
                    name=plaid_account.name,
                    institution_name=institution_name,
                    account_type=plaid_account.account_type,
                    account_subtype=plaid_account.account_subtype,
                    currency=plaid_account.currency,
                    current_balance=plaid_account.current_balance,
                    available_balance=plaid_account.available_balance,
                    mask=plaid_account.mask,
                    source=AccountSource.PLAID.value,
                    external_account_id=plaid_account.external_account_id,
                    connector_credential_id=credential.id,
                )
            )

        self.db.commit()
        for account in linked_accounts:
            # Idempotent either way (SyncJob's idempotency key guards it),
            # so it's simplest to kick every returned account rather than
            # distinguish newly-created from already-linked.
            sync_account.delay(str(account.id))
        return linked_accounts
