"""Application configuration.

Values come from the environment (12-factor). Locally that means a ``.env`` file;
in Azure it means Container Apps environment variables and Key Vault references
resolved by Managed Identity — never secrets baked into the image.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- environment ---
    app_env: Literal["local", "dev", "test", "staging", "prod"] = "local"
    log_level: str = "INFO"

    # --- HTTP ---
    api_host: str = "0.0.0.0"  # noqa: S104 - bind-all is intentional inside the container
    api_port: int = 8000
    # NoDecode: let the validator below split the CSV; don't JSON-parse the raw value.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # --- data stores ---
    database_url: str = "postgresql+asyncpg://tracker:tracker@localhost:5432/tracker"
    redis_url: str = "redis://localhost:6379/0"
    db_echo: bool = False

    # --- local dev auth stub ---
    # Mints HS256 tokens shaped like Entra ID access tokens so the whole
    # authorization stack can run without a tenant. See docs/adr/0002.
    dev_auth_enabled: bool = True
    dev_auth_secret: str = "local-dev-only-not-a-real-secret-change-me"
    access_token_ttl_minutes: int = 60

    # --- Entra ID (real integration; inert while the stub is enabled) ---
    entra_tenant_id: str | None = None
    entra_api_audience: str | None = None
    entra_issuer: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env in ("staging", "prod")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
