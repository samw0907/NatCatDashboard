# backend/app/config.py

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the repo root, one level above backend/
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    environment: str = "development"
    cors_allowed_origins: str = "http://localhost:5173"

    # Railway provides both: DATABASE_URL (internal hostname, only resolves inside
    # Railway's own network) and DATABASE_PUBLIC_URL (external proxy, needed for
    # local dev / Alembic runs from this machine). Prefer the public one when both
    # are set. Same pattern as WildfireDashboard.
    database_url: str | None = None
    database_public_url: str | None = None

    # Shared secret required in the X-Admin-Token header by every write
    # endpoint (see auth.py). Unset means write endpoints are disabled.
    admin_token: str | None = None

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.database_public_url or self.database_url
        if not url:
            raise RuntimeError("DATABASE_URL or DATABASE_PUBLIC_URL must be set")
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
