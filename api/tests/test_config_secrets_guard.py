import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import Settings

_STRONG_SECRET = "a" * 40
_OTHER_STRONG_SECRET = "b" * 40
_PLACEHOLDER = "change-me-to-a-long-random-string-in-every-environment"
_REAL_ENCRYPTION_KEY = Fernet.generate_key().decode()


def _base_kwargs(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "database_url": "postgresql+psycopg://u:p@localhost:5432/db",
        "redis_url": "redis://localhost:6379/0",
        "jwt_secret": _STRONG_SECRET,
        "session_secret": _OTHER_STRONG_SECRET,
        "encryption_key": _REAL_ENCRYPTION_KEY,
    }
    kwargs.update(overrides)
    return kwargs


def test_development_allows_the_placeholder_secret() -> None:
    # Must not raise -- dev/test environments intentionally use throwaway
    # secrets, only production is guarded.
    Settings(environment="development", **_base_kwargs(jwt_secret=_PLACEHOLDER, session_secret=""))


def test_development_defaults_session_secret_to_jwt_secret_when_blank() -> None:
    settings = Settings(environment="development", **_base_kwargs(session_secret=""))
    assert settings.session_secret == settings.jwt_secret


def test_production_rejects_the_placeholder_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        Settings(environment="production", **_base_kwargs(jwt_secret=_PLACEHOLDER))


def test_production_rejects_a_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="32 characters"):
        Settings(environment="production", **_base_kwargs(jwt_secret="too-short"))


def test_production_rejects_session_secret_equal_to_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="session_secret must be set to its own value"):
        Settings(environment="production", **_base_kwargs(session_secret=_STRONG_SECRET))


def test_production_accepts_two_distinct_strong_secrets() -> None:
    # Must not raise.
    Settings(environment="production", **_base_kwargs())


def test_missing_encryption_key_fails_to_boot_in_any_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression: encryption_key used to default to a real, valid, but
    # publicly-known Fernet key, silently working in every environment
    # except one spelled exactly "production" -- a deploy that simply
    # forgot to set ENCRYPTION_KEY booted fine and encrypted every
    # connector_credential/oauth_accounts token with a key anyone reading
    # the source already knows. It must now fail to boot in *every*
    # environment when omitted, the same way jwt_secret/database_url do,
    # not just be rejected when it's the known placeholder.
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    kwargs = _base_kwargs()
    del kwargs["encryption_key"]
    with pytest.raises(ValidationError):
        Settings(environment="development", _env_file=None, **kwargs)


def test_malformed_encryption_key_is_rejected_in_any_environment() -> None:
    with pytest.raises(ValidationError, match="not a valid Fernet key"):
        Settings(environment="development", **_base_kwargs(encryption_key="not-a-fernet-key"))


def test_production_rejects_the_placeholder_encryption_key() -> None:
    with pytest.raises(ValidationError, match="encryption_key is still set"):
        Settings(
            environment="production",
            **_base_kwargs(encryption_key="VMLWJOtffXQuSHEHlgUY9mc_2Tpuzg_zr1yzKjqtImY="),
        )
