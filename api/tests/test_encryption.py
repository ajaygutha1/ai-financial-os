import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.encryption import DecryptionError, decrypt, encrypt
from app.models.connector_credential import ConnectorCredential
from app.models.user import OAuthAccount, User


def test_encrypt_decrypt_round_trips() -> None:
    plaintext = "super-secret-access-token"
    ciphertext = encrypt(plaintext)

    assert ciphertext != plaintext
    assert decrypt(ciphertext) == plaintext


def test_decrypt_rejects_garbage_ciphertext() -> None:
    with pytest.raises(DecryptionError):
        decrypt("not-a-real-fernet-token")


def test_connector_credential_token_is_encrypted_at_rest(
    db_session: Session, test_user: User
) -> None:
    plaintext = "plaid-access-token-abc123"
    credential = ConnectorCredential(
        id=uuid.uuid4(),
        user_id=test_user.id,
        provider="plaid",
        access_token_enc=plaintext,
    )
    db_session.add(credential)
    db_session.commit()

    # Bypass the ORM's type decorator to read the raw column value straight
    # from Postgres -- this is the actual proof that ciphertext, not
    # plaintext, is what's stored.
    raw_value = db_session.execute(
        text("SELECT access_token_enc FROM connector_credential WHERE id = :id"),
        {"id": credential.id},
    ).scalar_one()
    assert raw_value != plaintext

    db_session.expire(credential)
    reloaded = db_session.get(ConnectorCredential, credential.id)
    assert reloaded is not None
    assert reloaded.access_token_enc == plaintext


def test_oauth_account_token_is_encrypted_at_rest(db_session: Session, test_user: User) -> None:
    plaintext = "google-refresh-token-xyz789"
    oauth_account = OAuthAccount(
        id=uuid.uuid4(),
        user_id=test_user.id,
        provider="google",
        provider_account_id="google-sub-123",
        refresh_token_enc=plaintext,
    )
    db_session.add(oauth_account)
    db_session.commit()

    raw_value = db_session.execute(
        text("SELECT refresh_token_enc FROM oauth_accounts WHERE id = :id"),
        {"id": oauth_account.id},
    ).scalar_one()
    assert raw_value != plaintext

    db_session.expire(oauth_account)
    reloaded = db_session.get(OAuthAccount, oauth_account.id)
    assert reloaded is not None
    assert reloaded.refresh_token_enc == plaintext


def test_null_token_stays_null(db_session: Session, test_user: User) -> None:
    credential = ConnectorCredential(
        id=uuid.uuid4(), user_id=test_user.id, provider="coinbase", access_token_enc=None
    )
    db_session.add(credential)
    db_session.commit()
    db_session.expire(credential)

    reloaded = db_session.get(ConnectorCredential, credential.id)
    assert reloaded is not None
    assert reloaded.access_token_enc is None
