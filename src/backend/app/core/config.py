from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Supermarket Evolution"
    app_version: str = "0.1.0"
    database_url: str = "sqlite+aiosqlite:///./supermarket-evolution.db"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    local_app_token: str | None = None
    schema_version: str = "0001"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SUPERMARKET_", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
