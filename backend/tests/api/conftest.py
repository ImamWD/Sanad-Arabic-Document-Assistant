"""Fixtures for the API tests.

The tests run against `<POSTGRES_DB>_test_<random>`: a database created for this pytest run,
migrated with Alembic and dropped afterwards. They never touch the database `make up` uses,
and two runs on the same Postgres don't collide. Each test starts from TRUNCATE plus the init
steps (programmes and demo accounts), and gets its own app and TestClient.

Identity is switched per request with `as_(who)`, which sends that principal's session cookie;
the client's own cookie jar is kept empty.
"""

import secrets
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import sqlalchemy
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from alembic import command
from sanad import init
from sanad.api.main import create_app
from sanad.core import passwords
from sanad.core.config import Settings, get_settings
from sanad.core.db import create_sync_engine
from sanad.core.security import CSRF_HEADER, SESSION_COOKIE

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic" / "alembic.ini"
CSRF = {CSRF_HEADER: "1"}
PRINCIPALS = ("anonymous", "guest", "viewer", "editor", "admin")
# The hasher the app ships with, kept before the fast one below replaces it for the tests.
PRODUCTION_HASHER = passwords._hasher

Sessions = dict[str, str]


def alembic_config(connection: sqlalchemy.Connection) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["connection"] = connection
    cfg.attributes["configure_logger"] = False
    return cfg


def demo_password(settings: Settings, who: str) -> str:
    secret: str = getattr(settings, f"demo_{who}_password").get_secret_value()
    return secret


def sign_in(client: TestClient, settings: Settings, who: str) -> str:
    """Sign in as a demo principal and return the session token (the jar is left empty)."""
    client.cookies.clear()
    if who == "guest":
        response = client.post("/api/auth/guest", json={}, headers=CSRF)
    else:
        credentials = {"email": f"{who}@sanad.example", "password": demo_password(settings, who)}
        response = client.post("/api/auth/login", json=credentials, headers=CSRF)
    assert response.status_code == 200, response.text
    token = response.cookies[SESSION_COOKIE]
    client.cookies.clear()
    return token


def as_(token: str | None) -> dict[str, str]:
    """Headers for one request: the CSRF header, plus the session cookie if `token` is given."""
    headers = dict(CSRF)
    if token is not None:
        headers["Cookie"] = f"{SESSION_COOKIE}={token}"
    return headers


@pytest.fixture(scope="session", autouse=True)
def fast_password_hashing() -> Iterator[None]:
    """argon2id with minimal cost, so the suite doesn't spend seconds hashing."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(passwords, "_hasher", PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
        passwords._dummy_hash.cache_clear()
        yield
    passwords._dummy_hash.cache_clear()


@pytest.fixture(scope="session")
def settings() -> Iterator[Settings]:
    base = get_settings()
    name = f"{base.postgres_db}_test_{secrets.token_hex(4)}"
    server = sqlalchemy.create_engine(base.database_url, isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("POSTGRES_DB", name)
            get_settings.cache_clear()
            test_settings = get_settings()
            engine = create_sync_engine(test_settings)
            with engine.begin() as conn:
                command.upgrade(alembic_config(conn), "head")
            engine.dispose()
            yield test_settings
    finally:
        get_settings.cache_clear()
        with server.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        server.dispose()


@pytest.fixture(scope="session")
def engine(settings: Settings) -> Iterator[sqlalchemy.Engine]:
    """Sync engine on the test database, for arranging and inspecting rows directly."""
    eng = create_sync_engine(settings)
    yield eng
    eng.dispose()


@pytest.fixture
def seeded(settings: Settings, engine: sqlalchemy.Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE users, sessions, programmes, audit_events RESTART IDENTITY CASCADE")
        )
    init.run(settings)


@pytest.fixture
def set_env(settings: Settings) -> Iterator[Callable[..., None]]:
    """Change settings for one test: set_env(guest_mode="off")."""
    with pytest.MonkeyPatch.context() as mp:

        def apply(**env: str) -> None:
            for key, value in env.items():
                mp.setenv(key.upper(), value)
            get_settings.cache_clear()

        yield apply
    get_settings.cache_clear()


@pytest.fixture
def app(seeded: None) -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def sessions(client: TestClient, settings: Settings) -> Sessions:
    """A fresh session token for every signed-in principal."""
    return {who: sign_in(client, settings, who) for who in PRINCIPALS if who != "anonymous"}


@pytest.fixture
def ids(engine: sqlalchemy.Engine, seeded: None) -> dict[str, uuid.UUID]:
    """Account ids by principal, for path parameters: {"viewer_id": …, "admin_id": …}."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT email, id FROM users")).all()
    return {f"{email.split('@')[0]}_id": user_id for email, user_id in rows}
