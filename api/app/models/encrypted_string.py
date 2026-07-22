from typing import Any

from sqlalchemy import String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from app.core.encryption import decrypt, encrypt


class EncryptedString(TypeDecorator[str]):
    """Transparent field-level encryption (Milestone 8) -- callers read and
    write plain strings exactly as before; encryption happens at the ORM
    boundary so no repository/service call site can forget to encrypt
    before persisting or decrypt before using a value. Column storage is
    still a plain VARCHAR (ciphertext is base64 text), so no migration is
    needed beyond re-encrypting whatever data already exists."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return decrypt(value)
