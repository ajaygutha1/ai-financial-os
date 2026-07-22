from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.exceptions import AppError


class DecryptionError(AppError):
    """Raised when stored ciphertext can't be decrypted -- almost always
    means encryption_key changed (or rotated) without re-encrypting existing
    rows, not a transient error worth retrying."""

    default_message = "Stored credential could not be decrypted."


def _fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.encryption_key.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError() from exc
