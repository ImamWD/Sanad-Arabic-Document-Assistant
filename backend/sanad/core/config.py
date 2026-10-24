"""Runtime configuration, read from the environment (see .env.example)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    """Every field maps to an upper-case environment variable of the same name."""

    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    database_url: SecretStr = SecretStr("postgresql+psycopg://sanad:sanad@db:5432/sanad")
    ml_base_url: str = "http://ml:8001"
    health_timeout_seconds: float = Field(default=2.0, gt=0)
    worker_idle_seconds: float = Field(default=30.0, gt=0)
    log_level: LogLevel = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
