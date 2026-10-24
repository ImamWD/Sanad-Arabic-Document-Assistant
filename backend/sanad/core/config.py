"""Runtime configuration, read from the environment (see .env.example)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    """Every field maps to an upper-case environment variable of the same name."""

    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    postgres_host: str = "db"
    postgres_port: int = Field(default=5432, gt=0, lt=65536)
    postgres_user: str = "sanad"
    postgres_password: SecretStr = SecretStr("sanad")
    postgres_db: str = "sanad"
    ml_base_url: str = "http://ml:8001"
    health_timeout_seconds: float = Field(default=2.0, gt=0)
    worker_idle_seconds: float = Field(default=30.0, gt=0)
    log_level: LogLevel = "INFO"

    @property
    def database_url(self) -> URL:
        """Built from parts, so the password may contain any character (no manual escaping)."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
