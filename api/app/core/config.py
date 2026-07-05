from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str
    redis_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14

    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    oauth_redirect_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"

    cors_allow_origins: str = "http://localhost:3000"

    @property
    def session_secret(self) -> str:
        """Signs the transient OAuth 'state' cookie. Distinct in principle from
        jwt_secret (different blast radius), but sharing one dev secret is fine
        pre-M8 security hardening, where secrets management gets its own pass."""
        return self.jwt_secret

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
