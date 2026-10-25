"""Fixtures for the retrieval and ask tests.

Unit tests use the fakes in `fakes.py` and need nothing running. DB-backed tests run against
`<POSTGRES_DB>_retrieval_<random>`, created and migrated for this pytest run and dropped
afterwards; never the database `make up` uses. Sign-in reuses B2's helpers.
"""

import secrets
import uuid
from collections.abc import Callable, Iterator

import pytest
import sqlalchemy
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from alembic import command
from sanad import init
from sanad.api.ask import get_pipeline
from sanad.api.main import create_app
from sanad.core.config import Settings, get_settings
from sanad.core.db import create_sync_engine
from sanad.core.models import User
from sanad.llm.settings import get_llm_settings
from sanad.retrieval.pipeline import AskPipeline
from sanad.retrieval.search import SqlRetriever
from sanad.retrieval.settings import get_retrieval_settings
from sanad.retrieval.store import SqlQueryStore
from tests.api.conftest import (  # noqa: F401  (fast_password_hashing is an autouse fixture)
    alembic_config,
    fast_password_hashing,
    sign_in,
)
from tests.retrieval.corpus import FakeMl, insert_corpus
from tests.retrieval.fakes import GroundedLlm


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def settings() -> Iterator[Settings]:
    base = get_settings()
    name = f"{base.postgres_db}_retrieval_{secrets.token_hex(4)}"
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
    eng = create_sync_engine(settings)
    yield eng
    eng.dispose()


@pytest.fixture
def accounts(settings: Settings, engine: sqlalchemy.Engine) -> dict[str, uuid.UUID]:
    """A clean database (questions and documents go with the users) holding B2's programmes
    and demo accounts; returns user ids by name."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE users, sessions, programmes, audit_events, llm_perf_samples "
                "RESTART IDENTITY CASCADE"
            )
        )
    for step in (init.seed_programmes, init.seed_accounts):
        with Session(engine) as db, db.begin():
            step(db, settings)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT email, id FROM users")).all()
    return {email.split("@")[0]: user_id for email, user_id in rows}


@pytest.fixture
def corpus(engine: sqlalchemy.Engine, accounts: dict[str, uuid.UUID]) -> dict[str, uuid.UUID]:
    """The synthetic corpus of corpus.py; document ids by slug."""
    return insert_corpus(engine, accounts["editor"])


@pytest.fixture
def users(engine: sqlalchemy.Engine, accounts: dict[str, uuid.UUID]) -> dict[str, User]:
    """The demo accounts as detached User objects, for calling retrieval directly."""
    with Session(engine, expire_on_commit=False) as db:
        found = db.scalars(select(User)).all()
        db.expunge_all()
    return {u.email.split("@")[0]: u for u in found}


@pytest.fixture
def ml() -> FakeMl:
    return FakeMl()


@pytest.fixture
def llm() -> GroundedLlm:
    return GroundedLlm()


@pytest.fixture
def app(accounts: dict[str, uuid.UUID], ml: FakeMl, llm: GroundedLlm) -> FastAPI:
    """The real app and the real SQL retrieval and store, with the fake ml service and a fake
    LLM that answers only from what is in its excerpts."""
    application = create_app()

    def pipeline(request: Request) -> AskPipeline:
        engine = request.app.state.db_engine
        retrieval = get_retrieval_settings()
        return AskPipeline(
            retriever=SqlRetriever(engine, ml, retrieval),
            store=SqlQueryStore(engine),
            provider=llm,
            queue=request.app.state.generation_queue,
            retrieval=retrieval,
            llm=get_llm_settings(),
        )

    application.dependency_overrides[get_pipeline] = pipeline
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def sessions(client: TestClient, settings: Settings) -> dict[str, str]:
    return {who: sign_in(client, settings, who) for who in ("guest", "viewer", "editor", "admin")}


@pytest.fixture
def set_env(settings: Settings) -> Iterator[Callable[..., None]]:
    """Change settings for one test: set_env(sse_ping_seconds="0.05")."""
    caches = (get_settings, get_llm_settings, get_retrieval_settings)
    with pytest.MonkeyPatch.context() as mp:

        def apply(**env: str) -> None:
            for key, value in env.items():
                mp.setenv(key.upper(), value)
            for cache in caches:
                cache.cache_clear()

        yield apply
    for cache in caches:
        cache.cache_clear()
