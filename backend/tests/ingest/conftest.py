"""Fixtures for the ingestion and documents tests.

DB-backed tests run against `<POSTGRES_DB>_ingest_<random>`, a database created and migrated
for this pytest run and dropped afterwards; never the database `make up` uses. Files go to a
temporary FILES_DIR. Sign-in reuses B2's helpers, so the API is exercised with real sessions.

Tests that need the running stack (the real ml service, the seeded corpus) are marked
`live` and skip with a reason when it isn't there.
"""

import hashlib
import json
import secrets
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
import sqlalchemy
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from alembic import command
from sanad import init
from sanad.api.main import create_app
from sanad.core.config import Settings, get_settings
from sanad.core.db import create_sync_engine
from sanad.documents.models import DocStatus, Document
from sanad.documents.storage import original_path, resolve
from sanad.ingest.filetypes import FileType
from sanad.ingest.settings import IngestSettings, get_ingest_settings
from sanad.text.arabic import normalize_for_search
from tests.api.conftest import (  # noqa: F401  (fast_password_hashing is an autouse fixture)
    alembic_config,
    fast_password_hashing,
    sign_in,
)

REPO = Path(__file__).resolve().parents[3]
SEED = REPO / "seed"
BAD = SEED / "bad"
MANIFEST: dict[str, Any] = json.loads((SEED / "manifest.json").read_text(encoding="utf-8"))
SEED_ENTRIES: list[dict[str, Any]] = MANIFEST["documents"]

needs_seed_files = pytest.mark.skipif(
    not (SEED / "documents").is_dir() or not BAD.is_dir(),
    reason="seed/documents and seed/bad are rendered by C1b (make render-seed)",
)


def ml_url() -> str:
    return get_settings().ml_base_url


def ml_is_up() -> bool:
    try:
        return httpx2.get(f"{ml_url()}/health", timeout=3).status_code == 200
    except httpx2.HTTPError:
        return False


@pytest.fixture(scope="session")
def files_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("files")


@pytest.fixture(scope="session")
def settings(files_dir: Path) -> Iterator[Settings]:
    base = get_settings()
    name = f"{base.postgres_db}_ingest_{secrets.token_hex(4)}"
    server = sqlalchemy.create_engine(base.database_url, isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("POSTGRES_DB", name)
            mp.setenv("FILES_DIR", str(files_dir))
            mp.setenv("SEED_DIR", str(SEED))
            get_settings.cache_clear()
            get_ingest_settings.cache_clear()
            test_settings = get_settings()
            engine = create_sync_engine(test_settings)
            with engine.begin() as conn:
                command.upgrade(alembic_config(conn), "head")
            engine.dispose()
            yield test_settings
    finally:
        get_settings.cache_clear()
        get_ingest_settings.cache_clear()
        with server.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        server.dispose()


@pytest.fixture(scope="session")
def ingest_settings(settings: Settings) -> IngestSettings:
    return get_ingest_settings()


@pytest.fixture(scope="session")
def engine(settings: Settings) -> Iterator[sqlalchemy.Engine]:
    eng = create_sync_engine(settings)
    yield eng
    eng.dispose()


@pytest.fixture
def accounts(settings: Settings, engine: sqlalchemy.Engine) -> dict[str, uuid.UUID]:
    """A clean database with B2's programmes and demo accounts; returns user ids by name."""
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE users, sessions, programmes, audit_events RESTART IDENTITY CASCADE")
        )
    for step in (init.seed_programmes, init.seed_accounts):
        with Session(engine) as db, db.begin():
            step(db, settings)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT email, id FROM users")).all()
    return {email.split("@")[0]: user_id for email, user_id in rows}


DocumentFactory = Callable[..., Document]


@pytest.fixture
def make_document(
    engine: sqlalchemy.Engine, accounts: dict[str, uuid.UUID], ingest_settings: IngestSettings
) -> DocumentFactory:
    """Insert a document row (and its file) directly, bypassing the upload route."""

    def make(
        *,
        source: Path | None = None,
        content: bytes = b"%PDF-1.4 placeholder",
        file_type: FileType = FileType.PDF,
        title: str = "التقرير السنوي 2021",
        status: DocStatus = DocStatus.READY,
        **fields: Any,
    ) -> Document:
        data = source.read_bytes() if source is not None else content
        if source is not None:
            file_type = FileType(source.suffix.lstrip("."))
        document_id = uuid.uuid4()
        stored = original_path(document_id, file_type)
        path = resolve(ingest_settings.files_dir, stored)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        values: dict[str, Any] = {
            "id": document_id,
            "title": title,
            "title_norm": normalize_for_search(title),
            "original_filename": source.name if source else f"{document_id}.{file_type.value}",
            "file_path": stored,
            "viewer_path": stored if file_type is FileType.PDF else None,
            "file_type": file_type,
            "uploaded_by": accounts["editor"],
            "status": status,
            "sha256": hashlib.sha256(data + document_id.bytes).hexdigest(),
            "size_bytes": len(data),
            "error_code": "FILE_CORRUPT" if status is DocStatus.FAILED else None,
            **fields,
        }
        with Session(engine, expire_on_commit=False) as db, db.begin():
            document = Document(**values)
            db.add(document)
        return document

    return make


@pytest.fixture
def app(accounts: dict[str, uuid.UUID]) -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def sessions(client: TestClient, settings: Settings) -> dict[str, str]:
    return {who: sign_in(client, settings, who) for who in ("guest", "viewer", "editor", "admin")}
