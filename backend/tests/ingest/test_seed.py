"""The init step that registers the seed corpus, and revision 0002_documents."""

import hashlib
import json
import secrets
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy
from alembic.script import ScriptDirectory
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from alembic import command
from sanad import init
from sanad.core.config import Settings
from sanad.documents.models import DocStatus, Document
from sanad.documents.seed import register_seed_documents
from sanad.ingest.settings import IngestSettings
from tests.api.conftest import alembic_config
from tests.ingest.conftest import SEED, SEED_ENTRIES, needs_seed_files

CATEGORIES = {
    "annual_report": "annual_report",
    "donor_agreement": "donor_agreement",
    "evaluation": "programme_evaluation",
    "survey": "field_survey",
    "budget": "budget",
    "board_minutes": "board_minutes",
}


def run_step(engine: sqlalchemy.Engine, settings: Settings) -> None:
    with Session(engine) as db, db.begin():
        register_seed_documents(db, settings)


def seed_rows(engine: sqlalchemy.Engine) -> dict[str, Document]:
    with Session(engine) as db:
        documents = db.scalars(select(Document).where(Document.is_seed.is_(True))).all()
        return {d.original_filename: d for d in documents}


def test_the_seed_step_runs_after_programmes_and_accounts() -> None:
    names = [name for name, _ in init.STEPS]
    assert names.index("seed documents") > names.index("accounts") > names.index("programmes")


@needs_seed_files
def test_every_manifest_document_is_registered_once(
    engine: sqlalchemy.Engine,
    settings: Settings,
    ingest_settings: IngestSettings,
    accounts: dict[str, uuid.UUID],
) -> None:
    run_step(engine, settings)
    run_step(engine, settings)  # idempotent

    rows = seed_rows(engine)
    assert sorted(rows) == sorted(e["file"] for e in SEED_ENTRIES)
    with Session(engine) as db:
        codes = {pid: code for pid, code in db.execute(text("SELECT id, code FROM programmes"))}
    for entry in SEED_ENTRIES:
        document = rows[entry["file"]]
        assert document.status is DocStatus.QUEUED
        assert document.file_type == entry["format"]
        assert document.category == CATEGORIES[entry["category"]]
        assert document.year == entry["year"]
        assert codes.get(document.programme_id) == entry["programme"]
        assert document.restricted is bool(entry.get("restricted", False))
        assert document.is_archived is bool(entry.get("archived", False))
        assert document.uploaded_by == accounts["admin"]
        expected_title = entry["title_en"] if entry["language"] == "en" else entry["title_ar"]
        assert document.title == expected_title
        stored = ingest_settings.files_dir / document.file_path
        assert stored.read_bytes() == (SEED / "documents" / entry["file"]).read_bytes()
        assert document.file_path == f"originals/{document.id}.{entry['format']}"


def fake_seed(tmp_path: Path, entries: list[dict[str, Any]]) -> Path:
    seed = tmp_path / "seed"
    (seed / "documents").mkdir(parents=True)
    manifest = json.loads((SEED / "manifest.json").read_text(encoding="utf-8"))
    manifest["documents"] = entries
    (seed / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), "utf-8")
    return seed


def entry(file: str, **extra: Any) -> dict[str, Any]:
    return {
        "doc_id": file.split(".")[0],
        "file": file,
        "format": file.split(".")[1],
        "title_ar": "وثيقة تجريبية",
        "title_en": "Test document",
        "category": "budget",
        "year": 2024,
        "programme": None,
        "language": "ar",
        **extra,
    }


@pytest.fixture
def seed_dir_settings(
    tmp_path: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    seed = fake_seed(
        tmp_path,
        [
            entry("restricted.pdf", restricted=True),
            entry("archived.pdf", archived=True),
            entry("missing.pdf"),
            entry("plain.txt", category="survey", programme="WASH", language="en"),
        ],
    )
    (seed / "documents" / "restricted.pdf").write_bytes(b"%PDF-1.4 restricted")
    (seed / "documents" / "archived.pdf").write_bytes(b"%PDF-1.4 archived")
    (seed / "documents" / "plain.txt").write_text("Field notes.", encoding="utf-8")
    yield seed


def test_flags_and_missing_files(
    engine: sqlalchemy.Engine,
    settings: Settings,
    accounts: dict[str, uuid.UUID],
    seed_dir_settings: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run_step(engine, settings.model_copy(update={"seed_dir": seed_dir_settings}))

    rows = seed_rows(engine)
    assert sorted(rows) == ["archived.pdf", "plain.txt", "restricted.pdf"]
    assert (rows["restricted.pdf"].restricted, rows["restricted.pdf"].is_archived) == (True, False)
    assert (rows["archived.pdf"].restricted, rows["archived.pdf"].is_archived) == (False, True)
    plain = rows["plain.txt"]
    assert (plain.restricted, plain.is_archived, plain.category) == (False, False, "field_survey")
    assert plain.title == "Test document"
    assert plain.programme_id is not None
    assert "1 seed documents have no rendered file" in caplog.text


def test_a_seed_file_identical_to_an_upload_is_skipped(
    engine: sqlalchemy.Engine,
    settings: Settings,
    accounts: dict[str, uuid.UUID],
    seed_dir_settings: Path,
    make_document: Any,
) -> None:
    data = (seed_dir_settings / "documents" / "restricted.pdf").read_bytes()
    existing = make_document(content=data)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE documents SET sha256 = :h WHERE id = :id"),
            {"h": hashlib.sha256(data).hexdigest(), "id": existing.id},
        )
    run_step(engine, settings.model_copy(update={"seed_dir": seed_dir_settings}))
    assert "restricted.pdf" not in seed_rows(engine)


def test_no_admin_means_no_owner(engine: sqlalchemy.Engine, settings: Settings) -> None:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users RESTART IDENTITY CASCADE"))
    with pytest.raises(RuntimeError, match="no admin"):
        run_step(engine, settings)


# --- revision 0002_documents -------------------------------------------------------------------


@pytest.fixture
def scratch_db(settings: Settings) -> Iterator[sqlalchemy.Engine]:
    name = f"{settings.postgres_db}_mig_{secrets.token_hex(3)}"
    server = sqlalchemy.create_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    engine = sqlalchemy.create_engine(settings.database_url.set(database=name))
    try:
        yield engine
    finally:
        engine.dispose()
        with server.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        server.dispose()


def test_0002_chains_onto_0001(engine: sqlalchemy.Engine) -> None:
    with engine.connect() as conn:
        script = ScriptDirectory.from_config(alembic_config(conn))
    revision = script.get_revision("0002_documents")
    assert revision is not None and revision.down_revision == "0001_core"


def test_0002_upgrades_and_downgrades_cleanly(scratch_db: sqlalchemy.Engine) -> None:
    def tables(conn: sqlalchemy.Connection) -> set[str]:
        return set(
            conn.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        )

    with scratch_db.begin() as conn:
        command.upgrade(alembic_config(conn), "0002_documents")
    with scratch_db.connect() as conn:
        assert {"documents", "document_pages", "chunks"} <= tables(conn)
        indexes = set(
            conn.scalars(text("SELECT indexname FROM pg_indexes WHERE tablename = 'chunks'"))
        )
        assert {"ix_chunks_embedding", "ix_chunks_tsv"} <= indexes
        method = conn.scalar(
            text(
                "SELECT am.amname FROM pg_class c JOIN pg_am am ON am.oid = c.relam"
                " WHERE c.relname = 'ix_chunks_embedding'"
            )
        )
        assert method == "hnsw"
    with scratch_db.begin() as conn:
        command.downgrade(alembic_config(conn), "0001_core")
    with scratch_db.connect() as conn:
        assert not {"documents", "document_pages", "chunks"} & tables(conn)
        assert conn.scalar(text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")) == 0
        assert conn.scalar(text("SELECT count(*) FROM pg_type WHERE typname = 'doc_status'")) == 0
        # 0001's enum stays: it belongs to 0001.
        assert conn.scalar(text("SELECT count(*) FROM pg_type WHERE typname = 'doc_category'")) == 1


def test_failed_status_and_error_code_go_together(
    engine: sqlalchemy.Engine, make_document: Any
) -> None:
    document = make_document(status=DocStatus.READY)
    with pytest.raises(sqlalchemy.exc.IntegrityError), engine.begin() as conn:
        conn.execute(
            text("UPDATE documents SET status = 'failed' WHERE id = :id"), {"id": document.id}
        )
