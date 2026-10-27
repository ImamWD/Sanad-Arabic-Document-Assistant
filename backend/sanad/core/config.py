"""Runtime configuration, read from the environment (see .env.example)."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
GuestMode = Literal["seed_only", "off"]
SanadEnv = Literal["demo", "production"]


class Settings(BaseSettings):
    """Every field maps to an upper-case environment variable of the same name."""

    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    # demo: the public defaults below work, with a startup warning (a clean `docker compose up`
    # must run with no .env). production: api and init refuse to start while any is in use.
    sanad_env: SanadEnv = "demo"

    postgres_host: str = "db"
    postgres_port: int = Field(default=5432, gt=0, lt=65536)
    postgres_user: str = "sanad"
    postgres_password: SecretStr = SecretStr("sanad")
    postgres_db: str = "sanad"
    ml_base_url: str = "http://ml:8001"
    health_timeout_seconds: float = Field(default=2.0, gt=0)
    worker_idle_seconds: float = Field(default=30.0, gt=0)
    log_level: LogLevel = "INFO"

    # Sessions (SYSTEM_DESIGN §9): opaque cookie, idle and absolute expiry.
    session_idle_minutes: int = Field(default=480, gt=0)
    session_absolute_hours: int = Field(default=168, gt=0)
    session_cookie_secure: bool = False
    # Login rate limiting: failed attempts allowed per window, per email and per client IP.
    login_window_seconds: int = Field(default=900, gt=0)
    login_max_failures_per_email: int = Field(default=5, gt=0)
    login_max_failures_per_ip: int = Field(default=20, gt=0)
    password_min_length: int = Field(default=10, ge=8)

    # seed_only: the guest sees seed documents only. off: guest login and guest sessions refused.
    guest_mode: GuestMode = "seed_only"
    # Demo account passwords, used only when `python -m sanad.init` first creates the accounts.
    demo_admin_password: SecretStr = SecretStr("admin-demo-2026")
    demo_editor_password: SecretStr = SecretStr("editor-demo-2026")
    demo_viewer_password: SecretStr = SecretStr("viewer-demo-2026")
    # seed/ (manifest.json and the seed corpus). The init service mounts it here.
    seed_dir: Path = Path("/app/seed")

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


# Settings whose default is public (it is in this repo) or unsafe on a real network.
_PUBLIC_SECRET_DEFAULTS = (
    "demo_admin_password",
    "demo_editor_password",
    "demo_viewer_password",
    "postgres_password",
)

INSECURE_DEFAULTS = "INSECURE_DEFAULTS"


class InsecureDefaultsError(RuntimeError):
    """SANAD_ENV=production with public defaults still in use. Startup and log only: it never
    reaches the API error envelope, so it carries a stable code but needs no translation."""

    code = INSECURE_DEFAULTS

    def __init__(self, names: list[str]) -> None:
        self.names = names
        super().__init__(
            f"{INSECURE_DEFAULTS}: SANAD_ENV=production refuses to start while these settings "
            f"keep their public defaults: {', '.join(names)}. Set them in .env (see .env.example)."
        )


def public_defaults_in_use(settings: Settings) -> list[str]:
    """Environment variable names of the settings still at their public default. Names only,
    never values."""
    names = [
        field.upper()
        for field in _PUBLIC_SECRET_DEFAULTS
        if getattr(settings, field).get_secret_value()
        == Settings.model_fields[field].get_default().get_secret_value()
    ]
    if not settings.session_cookie_secure:
        names.append("SESSION_COOKIE_SECURE")
    return names


def check_public_defaults(settings: Settings, logger: logging.Logger) -> None:
    """Run at api and init startup. production: raise InsecureDefaultsError naming every
    public default still in use. demo: log one warning with the same names."""
    names = public_defaults_in_use(settings)
    if not names:
        return
    if settings.sanad_env == "production":
        raise InsecureDefaultsError(names)
    logger.warning(
        "SANAD_ENV=demo: public defaults in use for %s. Fine for the demo; on a real deployment "
        "change them and set SANAD_ENV=production, which refuses to start until they are changed.",
        ", ".join(names),
    )
