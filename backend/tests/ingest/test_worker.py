"""The worker against a real database, with a fake ml service (fast, deterministic).

The real ml service is exercised in test_ml_live.py and on the running stack in
test_live_stack.py.
"""

import hashlib
import threading
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from sanad.core.errors import ErrorCode
from sanad.documents.models import Chunk, DocStatus, Document, DocumentPage
from sanad.ingest import worker as worker_module
from sanad.ingest.filetypes import FileType
from sanad.ingest.ml_client import MlClient, MlUnavailableError
from sanad.ingest.settings import IngestSettings
from sanad.ingest.worker import Claim, Worker
from tests.ingest.conftest import BAD, SEED, SEED_ENTRIES, DocumentFactory, needs_seed_files

DIM = 1024


class FakeMl:
    """Whitespace "tokens" and deterministic unit vectors."""

    model = "fake/bge-m3@test"

    def __init__(self, *, up: bool = True, fail_embed: bool = False) -> None:
        self.up = up
        self.fail_embed = fail_embed
        self.embedded = 0
        self.on_embed: Callable[[], None] = lambda: None

    def healthy(self) -> bool:
        return self.up

    def count_tokens(self, texts: Sequence[str]) -> list[int]:
        return [len(t.split()) for t in texts]

    def embed(
        self, texts: Sequence[str], on_batch: Callable[[], None] = lambda: None
    ) -> tuple[str, list[list[float]]]:
        if self.fail_embed:
            raise MlUnavailableError("/embed: ConnectError")
        self.on_embed()
        vectors = []
        for t in texts:
            seed = int.from_bytes(hashlib.sha256(t.encode()).digest()[:2], "big") % DIM
            vector = [0.0] * DIM
            vector[seed] = 1.0
            vectors.append(vector)
        self.embedded += len(texts)
        on_batch()
        return self.model, vectors

    def close(self) -> None:
        pass


@pytest.fixture
def ml() -> FakeMl:
    return FakeMl()


@pytest.fixture
def stop() -> threading.Event:
    return threading.Event()


@pytest.fixture
def worker(
    engine: sqlalchemy.Engine, ml: FakeMl, ingest_settings: IngestSettings, stop: threading.Event
) -> Worker:
    return Worker(engine, ml, ingest_settings, stop)


def row(engine: sqlalchemy.Engine, document_id: uuid.UUID) -> Document:
    with Session(engine, expire_on_commit=False) as db:
        document = db.get(Document, document_id)
        assert document is not None
        return document


def run_one(worker: Worker) -> DocStatus:
    claim = worker.claim()
    assert claim is not None
    return worker.process(claim)


@needs_seed_files
def test_a_seed_pdf_goes_to_ready_with_pages_and_chunks(
    worker: Worker, engine: sqlalchemy.Engine, make_document: DocumentFactory, ml: FakeMl
) -> None:
    entry = next(e for e in SEED_ENTRIES if e["file"] == "annual-report-2021.pdf")
    document = make_document(source=SEED / "documents" / entry["file"], status=DocStatus.QUEUED)

    assert run_one(worker) is DocStatus.READY

    stored = row(engine, document.id)
    assert stored.status is DocStatus.READY
    assert stored.page_count == entry["page_count"]
    assert stored.viewer_path == stored.file_path
    assert stored.language == "ar"
    assert stored.error_code is None and stored.ready_at is not None
    assert stored.attempts == 1
    with Session(engine) as db:
        pages = db.scalars(
            select(DocumentPage).where(DocumentPage.document_id == document.id)
        ).all()
        chunks = db.scalars(
            select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.chunk_index)
        ).all()
        page_text = {p.page_number: p.text for p in pages}
        assert sorted(page_text) == list(range(1, entry["page_count"] + 1))
        assert len(chunks) >= entry["page_count"]
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
        for chunk in chunks:
            # Every chunk is a slice of the cleaned text of its own viewer page.
            assert chunk.text == page_text[chunk.page_number][chunk.char_start : chunk.char_end]
            assert chunk.embedding_model == FakeMl.model
            assert len(chunk.embedding) == DIM
            assert chunk.token_count <= 512
        # The generated tsvector indexes the normalised text: tatweel is gone.
        hits = db.scalar(
            select(func.count())
            .select_from(Chunk)
            .where(
                Chunk.document_id == document.id,
                Chunk.tsv.op("@@")(func.to_tsquery("simple", "التعليم")),
            )
        )
        assert hits and hits > 0
    assert ml.embedded == len(chunks)


@needs_seed_files
@pytest.mark.parametrize(
    ("fixture", "code"),
    [
        ("truncated.pdf", ErrorCode.FILE_CORRUPT),
        ("encrypted.pdf", ErrorCode.PDF_ENCRYPTED),
        ("scanned-no-text.pdf", ErrorCode.NO_TEXT_LAYER),
        ("empty.docx", ErrorCode.EMPTY_DOCUMENT),
        ("not-a-pdf.pdf", ErrorCode.UNSUPPORTED_TYPE),
    ],
)
def test_every_bad_fixture_fails_with_its_code(
    worker: Worker,
    engine: sqlalchemy.Engine,
    make_document: DocumentFactory,
    fixture: str,
    code: ErrorCode,
) -> None:
    document = make_document(source=BAD / fixture, status=DocStatus.QUEUED)

    assert run_one(worker) is DocStatus.FAILED

    stored = row(engine, document.id)
    assert stored.status is DocStatus.FAILED
    assert stored.error_code == code.value
    # Params hold counts only: no text, no paths, no traceback.
    assert all(isinstance(v, int) for v in (stored.error_params or {}).values())
    with Session(engine) as db:
        assert db.scalar(select(func.count()).where(Chunk.document_id == document.id)) == 0


@needs_seed_files
def test_a_txt_in_windows_1256_is_converted_and_indexed(
    worker: Worker, engine: sqlalchemy.Engine, make_document: DocumentFactory
) -> None:
    entry = next(e for e in SEED_ENTRIES if e.get("encoding") == "windows-1256")
    document = make_document(source=SEED / "documents" / entry["file"], status=DocStatus.QUEUED)

    assert run_one(worker) is DocStatus.READY

    stored = row(engine, document.id)
    assert stored.viewer_path == f"viewer/{document.id}.pdf"
    assert stored.page_count == entry["page_count"]
    with Session(engine) as db:
        first = db.get(DocumentPage, (document.id, 1))
        assert first is not None and "مجلس" in first.text  # decoded, not mojibake


def test_the_claim_takes_the_oldest_queued_document_once(
    worker: Worker, engine: sqlalchemy.Engine, make_document: DocumentFactory
) -> None:
    first = make_document(status=DocStatus.QUEUED)
    second = make_document(status=DocStatus.QUEUED)
    make_document(status=DocStatus.READY)

    a, b = worker.claim(), worker.claim()

    assert a is not None and b is not None
    assert (a.document_id, b.document_id) == (first.id, second.id)
    assert worker.claim() is None
    assert row(engine, first.id).status is DocStatus.EXTRACTING
    assert row(engine, first.id).attempts == 1


def test_a_row_locked_by_another_worker_is_skipped(
    worker: Worker, engine: sqlalchemy.Engine, make_document: DocumentFactory
) -> None:
    first = make_document(status=DocStatus.QUEUED)
    second = make_document(status=DocStatus.QUEUED)
    with engine.connect() as other:
        other.execute(text("SELECT id FROM documents WHERE id = :id FOR UPDATE"), {"id": first.id})
        claim = worker.claim()
        assert claim is not None and claim.document_id == second.id
        other.rollback()


def test_stale_claims_are_requeued_then_failed(
    worker: Worker, engine: sqlalchemy.Engine, make_document: DocumentFactory
) -> None:
    retry = make_document(status=DocStatus.EXTRACTING, attempts=1)
    give_up = make_document(status=DocStatus.INDEXING, attempts=3)
    fresh = make_document(status=DocStatus.EXTRACTING, attempts=1)
    with engine.begin() as conn:
        conn.execute(
            update(Document)
            .where(Document.id.in_([retry.id, give_up.id]))
            .values(processing_started_at=func.now() - text("interval '2 hours'"))
        )
        conn.execute(
            update(Document).where(Document.id == fresh.id).values(processing_started_at=func.now())
        )

    assert worker.recover_stale() == (1, 1)

    assert row(engine, retry.id).status is DocStatus.QUEUED
    failed = row(engine, give_up.id)
    assert failed.status is DocStatus.FAILED and failed.error_code == "WORKER_TIMEOUT"
    assert row(engine, fresh.id).status is DocStatus.EXTRACTING


@needs_seed_files
def test_a_worker_that_lost_its_claim_writes_nothing(
    worker: Worker, engine: sqlalchemy.Engine, make_document: DocumentFactory, ml: FakeMl
) -> None:
    document = make_document(
        source=SEED / "documents" / "budget-2018.docx", status=DocStatus.QUEUED
    )
    claim = worker.claim()
    assert claim is not None

    def taken_over() -> None:  # stale recovery + another worker's claim, mid-indexing
        with engine.begin() as conn:
            conn.execute(update(Document).where(Document.id == document.id).values(attempts=2))

    ml.on_embed = taken_over
    assert worker.process(claim) is DocStatus.QUEUED
    stored = row(engine, document.id)
    assert stored.status is DocStatus.INDEXING and stored.attempts == 2
    with Session(engine) as db:
        assert db.scalar(select(func.count()).where(Chunk.document_id == document.id)) == 0


@needs_seed_files
def test_stopping_mid_document_puts_it_back_without_using_an_attempt(
    worker: Worker,
    engine: sqlalchemy.Engine,
    make_document: DocumentFactory,
    ml: FakeMl,
    stop: threading.Event,
) -> None:
    document = make_document(
        source=SEED / "documents" / "annual-report-2016.pdf", status=DocStatus.QUEUED
    )
    ml.on_embed = stop.set
    assert run_one(worker) is DocStatus.QUEUED
    stored = row(engine, document.id)
    assert stored.status is DocStatus.QUEUED and stored.attempts == 0


@needs_seed_files
def test_ml_outage_requeues_until_the_last_attempt(
    engine: sqlalchemy.Engine,
    make_document: DocumentFactory,
    ingest_settings: IngestSettings,
    stop: threading.Event,
) -> None:
    worker = Worker(engine, FakeMl(fail_embed=True), ingest_settings, stop, max_attempts=2)
    document = make_document(
        source=SEED / "documents" / "annual-report-2016.pdf", status=DocStatus.QUEUED
    )
    assert run_one(worker) is DocStatus.QUEUED
    assert row(engine, document.id).status is DocStatus.QUEUED
    assert run_one(worker) is DocStatus.FAILED
    stored = row(engine, document.id)
    assert stored.error_code == "ML_UNAVAILABLE" and stored.attempts == 2


def test_no_claim_while_ml_is_down(
    engine: sqlalchemy.Engine,
    make_document: DocumentFactory,
    ingest_settings: IngestSettings,
    stop: threading.Event,
) -> None:
    document = make_document(status=DocStatus.QUEUED)
    worker = Worker(engine, FakeMl(up=False), ingest_settings, stop)
    assert worker.tick() is False
    assert row(engine, document.id).status is DocStatus.QUEUED


def test_unexpected_errors_become_internal_error_with_a_reference(
    worker: Worker,
    engine: sqlalchemy.Engine,
    make_document: DocumentFactory,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(worker_module, "extract_document", explode)
    document = make_document(status=DocStatus.QUEUED)

    assert run_one(worker) is DocStatus.FAILED

    stored = row(engine, document.id)
    assert stored.error_code == "INTERNAL_ERROR"
    ref = (stored.error_params or {})["ref"]
    assert len(ref) == 12
    assert f"ref {ref}" in caplog.text  # the trace is in the server log, keyed by the ref


def test_retrying_a_document_replaces_its_pages(
    worker: Worker, engine: sqlalchemy.Engine, make_document: DocumentFactory, tmp_path: Path
) -> None:
    source = tmp_path / "note.txt"
    paragraphs = [
        "محضر اجتماع لجنة البرامج.",
        "ناقشت اللجنة خطة العمل للعام المقبل ووافقت عليها بالإجماع.",
    ]
    source.write_text("\n\n".join(paragraphs), encoding="utf-8")
    document = make_document(source=source, status=DocStatus.QUEUED)
    assert run_one(worker) is DocStatus.READY
    with engine.begin() as conn:
        conn.execute(
            update(Document)
            .where(Document.id == document.id)
            .values(status=DocStatus.QUEUED, attempts=0)
        )
    assert run_one(worker) is DocStatus.READY
    with Session(engine) as db:
        assert db.scalar(select(func.count()).where(DocumentPage.document_id == document.id)) == 1


def test_run_processes_queued_work_and_stops(
    make_document: DocumentFactory,
    engine: sqlalchemy.Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The loop: claims through LISTEN/poll, survives errors, returns once stopped."""
    stop = threading.Event()
    seen: list[Claim] = []

    def process(self: Worker, claim: Claim) -> DocStatus:
        seen.append(claim)
        stop.set()
        return DocStatus.READY

    monkeypatch.setattr(MlClient, "healthy", lambda self: True)
    monkeypatch.setattr(Worker, "process", process)
    document = make_document(status=DocStatus.QUEUED)
    thread = threading.Thread(target=worker_module.run, args=(stop, 0.2))
    thread.start()
    thread.join(timeout=20)
    assert not thread.is_alive()
    assert [c.document_id for c in seen] == [document.id]
    assert seen[0].file_type is FileType.PDF
