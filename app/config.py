"""Application settings, loaded from the environment.

Nothing here has a hardcoded credential: `DATABASE_URL` is required, so a missing
environment fails loudly at startup instead of silently falling back to a default.
"""

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "ci", "staging", "production"]


class Settings(BaseSettings):
    """Every environment variable the API and the worker read.

    Keep this in sync with `.env.example` — that file is the documented contract.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "DSS Internal"
    environment: Environment = "local"
    dev_mode: bool = False
    log_level: str = "INFO"

    database_url: PostgresDsn

    worker_poll_interval_seconds: float = 5.0


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, read from the environment once."""
    return Settings()
