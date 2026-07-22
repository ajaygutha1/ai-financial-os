from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Known placeholder values that must never reach a production deploy --
# checked explicitly rather than just "is this non-empty", since a copied
# .env.example satisfies non-empty while still being a publicly-known secret.
_PLACEHOLDER_SECRETS = {
    "change-me-to-a-long-random-string-in-every-environment",
    "change-me-to-a-different-long-random-string-in-every-environment",
}
_MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str
    redis_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    # Signs the transient OAuth "state" cookie -- distinct from jwt_secret
    # (different blast radius: a leaked session_secret only forges an OAuth
    # state, a leaked jwt_secret forges access/refresh tokens for any user).
    # Left blank in dev, where it falls back to jwt_secret for convenience;
    # production must set its own.
    session_secret: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    oauth_redirect_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"

    cors_allow_origins: str = "http://localhost:3000"

    # --- AI (Milestone 4) ---
    anthropic_api_key: str = ""
    # Opus-tier by default -- financial-advice quality is worth the cost, and
    # it's the user's call to downgrade, not a default we pick for them.
    ai_model: str = "claude-opus-4-8"
    ai_max_tokens: int = 8192
    ai_effort: str = "high"
    ai_max_tool_iterations: int = 6

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _apply_dev_fallbacks_and_guard_production(self) -> "Settings":
        if not self.session_secret:
            # Dev convenience only -- the production branch below requires
            # session_secret to be explicitly set (and different), so this
            # fallback can never silently reach a real deploy.
            self.session_secret = self.jwt_secret

        if self.environment == "production":
            self._require_strong_secret("jwt_secret", self.jwt_secret)
            self._require_strong_secret("session_secret", self.session_secret)
            if self.session_secret == self.jwt_secret:
                raise ValueError(
                    "session_secret must be set to its own value in production -- "
                    "reusing jwt_secret means a leak of one compromises both."
                )
        return self

    @staticmethod
    def _require_strong_secret(name: str, value: str) -> None:
        if value in _PLACEHOLDER_SECRETS:
            raise ValueError(
                f"{name} is still set to the .env.example placeholder value -- "
                "generate a real secret before running in production."
            )
        if len(value) < _MIN_SECRET_LENGTH:
            raise ValueError(
                f"{name} must be at least {_MIN_SECRET_LENGTH} characters in production "
                f"(got {len(value)})."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
