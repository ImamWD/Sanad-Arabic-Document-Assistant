"""The ingestion worker: claims queued documents and takes each one to `ready` or `failed`.

- **Claim.** `FOR UPDATE SKIP LOCKED` on the oldest queued row, so several workers never take
  the same document. The claim bumps `attempts`, and every later write checks that
  `attempts` still matches: a worker whose claim was recovered as stale can never overwrite
  the document after another worker has taken it.
- **Stale claims.** A document whose stage hasn't moved for WORKER_STALE_SECONDS (its worker
  died) goes back to the queue, or fails with WORKER_TIMEOUT after WORKER_MAX_ATTEMPTS.
  The worker refreshes `processing_started_at` between stages and embedding batches.
- **Failures** are stored as an error code with params (counts only), translated by the UI.
  An unexpected exception becomes INTERNAL_ERROR with a reference id; the stack trace goes
  to the server log only. Logs never contain document text (SQL parameters are hidden).
- **Waking up.** The API sends `NOTIFY sanad_ingest` after an upload or retry; the worker
  LISTENs, so new work starts at once. Without a notification it polls every
  WORKER_IDLE_SECONDS.
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg
import sqlalchemy
from sqlalchemy import and_, delete, func, insert, select, update

from sanad.core.config import Settings, get_settings
from sanad.core.errors import ErrorCode
from sanad.core.models import Programme
from sanad.documents.models import Chunk, DocLanguage, DocStatus, Document, DocumentPage
from sanad.ingest.errors import IngestionError
from sanad.ingest.filetypes import FileType
from sanad.ingest.ml_client import MlClient, MlService, MlUnavailableError
from sanad.ingest.pipeline import (
    Extracted,
    Indexed,
    embedding_context,
    extract_document,
    index_pages,
)
from sanad.ingest.settings import IngestSettings, get_ingest_settings
from sanad.text.arabic import normalize_for_search

logger = logging.getLogger(__name__)

NOTIFY_CHANNEL = "sanad_ingest"
# How often stale claims are looked for while the worker runs (also once at startup).
RECOVERY_INTERVAL_SECONDS = 60.0
_IN_PROGRESS = (DocStatus.EXTRACTING, DocStatus.INDEXING)


class _ReleaseError(Exception):
    """The worker is stopping, or lost its claim: leave the document to someone else."""


@dataclass(frozen=True)
class Claim:
    document_id: uuid.UUID
    attempt: int
    file_path: str
    file_type: FileType

    @property
    def owned(self) -> sqlalchemy.ColumnElement[bool]:
        return and_(
            Document.id == self.document_id,
            Document.attempts == self.attempt,
            Document.status.in_(_IN_PROGRESS),
        )


def create_engine(settings: Settings) -> sqlalchemy.Engine:
    # hide_parameters: a failed INSERT of pages or chunks must not print their text to the log.
    return sqlalchemy.create_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True)


class Worker:
    def __init__(
        self,
        engine: sqlalchemy.Engine,
        ml: MlService,
        settings: IngestSettings,
        stop: threading.Event,
        max_attempts: int | None = None,
    ) -> None:
        self.engine = engine
        self.ml = ml
        self.settings = settings
        self.stop = stop
        self.max_attempts = max_attempts or settings.worker_max_attempts

    # --- queue ------------------------------------------------------------------------------

    def recover_stale(self) -> tuple[int, int]:
        """(re-queued, failed) documents whose worker stopped moving."""
        cutoff = func.now() - func.make_interval(
            0, 0, 0, 0, 0, 0, self.settings.worker_stale_seconds
        )
        stale = and_(Document.status.in_(_IN_PROGRESS), Document.processing_started_at < cutoff)
        with self.engine.begin() as conn:
            requeued = conn.execute(
                update(Document)
                .where(stale, Document.attempts < self.max_attempts)
                .values(status=DocStatus.QUEUED, processing_started_at=None)
            ).rowcount
            failed = conn.execute(
                update(Document)
                .where(stale, Document.attempts >= self.max_attempts)
                .values(
                    status=DocStatus.FAILED,
                    error_code=ErrorCode.WORKER_TIMEOUT.value,
                    error_params={},
                    processing_started_at=None,
                )
            ).rowcount
        if requeued or failed:
            logger.warning("stale claims: %d re-queued, %d failed", requeued, failed)
        return requeued, failed

    def claim(self) -> Claim | None:
        oldest = (
            select(Document.id)
            .where(Document.status == DocStatus.QUEUED)
            .order_by(Document.uploaded_at, Document.id)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        with self.engine.begin() as conn:
            row = conn.execute(
                update(Document)
                .where(Document.id == oldest)
                .values(
                    status=DocStatus.EXTRACTING,
                    attempts=Document.attempts + 1,
                    processing_started_at=func.now(),
                    error_code=None,
                    error_params=None,
                )
                .returning(Document.id, Document.attempts, Document.file_path, Document.file_type)
            ).first()
        if row is None:
            return None
        return Claim(row.id, row.attempts, row.file_path, FileType(row.file_type))

    # --- one document -----------------------------------------------------------------------

    def _check(self, conn: sqlalchemy.Connection, claim: Claim) -> None:
        """Lock the row and make sure it is still ours (and we aren't stopping)."""
        if self.stop.is_set():
            raise _ReleaseError("stopping")
        owned = conn.execute(
            select(Document.id).where(claim.owned).with_for_update()
        ).scalar_one_or_none()
        if owned is None:
            raise _ReleaseError("claim lost")

    def _embedding_context(self, claim: Claim, language: DocLanguage) -> str:
        """The document's title, programme (named in the document's language) and year."""
        with self.engine.connect() as conn:
            title, year, name_ar, name_en = conn.execute(
                select(Document.title, Document.year, Programme.name_ar, Programme.name_en)
                .outerjoin(Programme, Programme.id == Document.programme_id)
                .where(Document.id == claim.document_id)
            ).one()
        return embedding_context(title, name_en if language is DocLanguage.EN else name_ar, year)

    def heartbeat(self, claim: Claim) -> None:
        with self.engine.begin() as conn:
            self._check(conn, claim)
            conn.execute(
                update(Document).where(claim.owned).values(processing_started_at=func.now())
            )

    def process(self, claim: Claim) -> DocStatus:
        """Take one claimed document to its next resting state; returns that state."""
        log = {"document_id": str(claim.document_id), "attempt": claim.attempt}
        started = time.monotonic()
        try:
            extracted = extract_document(
                claim.document_id, claim.file_path, claim.file_type, self.settings
            )
            self._store_pages(claim, extracted)
            indexed = index_pages(
                extracted.pages,
                self.ml,
                self.settings,
                lambda: self.heartbeat(claim),
                context=self._embedding_context(claim, extracted.language),
            )
            self._store_chunks(claim, indexed)
        except IngestionError as exc:
            self._finish_failed(claim, exc.code, exc.params)
            logger.info("document failed: %s %s", exc.code.value, log)
            return DocStatus.FAILED
        except MlUnavailableError as exc:
            if claim.attempt < self.max_attempts:
                self._requeue(claim, refund=False)
                logger.warning("ml unavailable (%s), document re-queued: %s", exc, log)
                return DocStatus.QUEUED
            self._finish_failed(claim, ErrorCode.ML_UNAVAILABLE, {})
            return DocStatus.FAILED
        except _ReleaseError as exc:
            if str(exc) == "stopping":
                self._requeue(claim, refund=True)
            logger.info("document released (%s): %s", exc, log)
            return DocStatus.QUEUED
        except Exception:
            ref = uuid.uuid4().hex[:12]
            logger.exception("ingestion error, ref %s: %s", ref, log)
            self._finish_failed(claim, ErrorCode.INTERNAL_ERROR, {"ref": ref})
            return DocStatus.FAILED
        logger.info(
            "document ready: %s, %d pages, %d chunks, %.1fs",
            log,
            len(extracted.pages),
            len(indexed.chunks),
            time.monotonic() - started,
        )
        return DocStatus.READY

    def _store_pages(self, claim: Claim, extracted: Extracted) -> None:
        with self.engine.begin() as conn:
            self._check(conn, claim)
            # A retried document starts clean (chunks cascade from their pages).
            conn.execute(delete(DocumentPage).where(DocumentPage.document_id == claim.document_id))
            conn.execute(
                insert(DocumentPage),
                [
                    {
                        "document_id": claim.document_id,
                        "page_number": number,
                        "text": text,
                        "text_norm": normalize_for_search(text),
                        "char_count": len(text),
                    }
                    for number, text in enumerate(extracted.pages, start=1)
                ],
            )
            conn.execute(
                update(Document)
                .where(claim.owned)
                .values(
                    status=DocStatus.INDEXING,
                    viewer_path=extracted.viewer_path,
                    page_count=len(extracted.pages),
                    language=extracted.language,
                    processing_started_at=func.now(),
                )
            )

    def _store_chunks(self, claim: Claim, indexed: Indexed) -> None:
        with self.engine.begin() as conn:
            self._check(conn, claim)
            conn.execute(delete(Chunk).where(Chunk.document_id == claim.document_id))
            if indexed.chunks:
                conn.execute(
                    insert(Chunk),
                    [
                        {
                            "document_id": claim.document_id,
                            "page_number": chunk.page_number,
                            "chunk_index": chunk.chunk_index,
                            "text": chunk.text,
                            "text_norm": normalize_for_search(chunk.text),
                            "char_start": chunk.char_start,
                            "char_end": chunk.char_end,
                            "token_count": chunk.token_count,
                            "embedding": vector,
                            "embedding_model": indexed.model,
                        }
                        for chunk, vector in zip(indexed.chunks, indexed.vectors, strict=True)
                    ],
                )
            conn.execute(
                update(Document)
                .where(claim.owned)
                .values(status=DocStatus.READY, ready_at=func.now(), processing_started_at=None)
            )

    def _finish_failed(self, claim: Claim, code: ErrorCode, params: dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(Document)
                .where(claim.owned)
                .values(
                    status=DocStatus.FAILED,
                    error_code=code.value,
                    error_params=params,
                    processing_started_at=None,
                )
            )

    def _requeue(self, claim: Claim, *, refund: bool) -> None:
        """Back to the queue. A shutdown gives the attempt back; an ml outage uses it up."""
        with self.engine.begin() as conn:
            conn.execute(
                update(Document)
                .where(claim.owned)
                .values(
                    status=DocStatus.QUEUED,
                    attempts=Document.attempts - (1 if refund else 0),
                    processing_started_at=None,
                )
            )

    def tick(self) -> bool:
        """Process one document if there is one (and ml is up); True if one was processed."""
        if not self.ml.healthy():
            return False
        claim = self.claim()
        if claim is None:
            return False
        self.process(claim)
        return True


class _Listener:
    """LISTEN sanad_ingest on its own autocommit connection."""

    def __init__(self, settings: Settings) -> None:
        self.conn = psycopg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password.get_secret_value(),
            dbname=settings.postgres_db,
            autocommit=True,
        )
        self.conn.execute(f"LISTEN {NOTIFY_CHANNEL}")

    def wait(self, stop: threading.Event, seconds: float) -> None:
        """Return on a notification, on stop, or after `seconds`."""
        deadline = time.monotonic() + seconds
        while not stop.is_set() and (remaining := deadline - time.monotonic()) > 0:
            for _ in self.conn.notifies(timeout=min(1.0, remaining), stop_after=1):
                return

    def close(self) -> None:
        self.conn.close()


def run(stop: threading.Event, idle_seconds: float) -> None:
    """The worker loop. Survives database and ml outages; returns once `stop` is set."""
    logger.info("worker started")
    # One line per ml request (a few per page) drowns the worker's own log.
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    settings = get_settings()
    ingest = get_ingest_settings()
    worker: Worker | None = None
    listener: _Listener | None = None
    next_recovery = 0.0
    try:
        while not stop.is_set():
            busy = False
            try:
                if worker is None:
                    ml = MlClient(
                        settings.ml_base_url, ingest.ml_timeout_seconds, ingest.embed_batch_size
                    )
                    worker = Worker(create_engine(settings), ml, ingest, stop)
                if listener is None:
                    listener = _Listener(settings)
                if time.monotonic() >= next_recovery:
                    worker.recover_stale()
                    next_recovery = time.monotonic() + RECOVERY_INTERVAL_SECONDS
                busy = worker.tick()
            except Exception as exc:
                logger.warning("worker loop: %s", type(exc).__name__)
                if listener is not None:
                    listener.close()
                    listener = None
            if not busy:
                if listener is not None:
                    listener.wait(stop, idle_seconds)
                else:
                    stop.wait(min(idle_seconds, 5.0))
    finally:
        if listener is not None:
            listener.close()
        if worker is not None:
            worker.ml.close()
            worker.engine.dispose()
        logger.info("worker stopped")
