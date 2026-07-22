import pytest
from pydantic import ValidationError

from app.core.config import Settings

_STRONG_SECRET = "a" * 40
_OTHER_STRONG_SECRET = "b" * 40
_PLACEHOLDER = "change-me-to-a-long-random-string-in-every-environment"


def _base_kwargs(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "database_url": "postgresql+psycopg://u:p@localhost:5432/db",
        "redis_url": "redis://localhost:6379/0",
        "jwt_secret": _STRONG_SECRET,
        "session_secret": _OTHER_STRONG_SECRET,
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
