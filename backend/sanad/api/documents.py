"""Documents: upload, Library listing, metadata, lifecycle, the viewer PDF and page text.

Every read goes through `visible_documents(user)`: a document a user may not see is a plain
404, exactly like one that doesn't exist (restricted documents for viewers and the guest,
anything but the seed corpus for the guest). Writes are for editors and admins.
"""

import hashlib
import logging
import os
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, BinaryIO, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi import Path as PathParam
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, Select, and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sanad.core import audit
from sanad.core.db import DbSession
from sanad.core.errors import ApiError, ErrorCode
from sanad.core.models import DocCategory, Programme, User
from sanad.core.security import CurrentUser, Role, require_role
from sanad.documents.access import can_see_restricted, visible_documents
from sanad.documents.models import (
    ACTIVE_INDEX_GENERATION,
    Chunk,
    DocLanguage,
    DocStatus,
    Document,
    DocumentPage,
)
from sanad.documents.storage import original_path, resolve
from sanad.ingest.errors import IngestionError
from sanad.ingest.filetypes import FileType, check_content, type_from_name
from sanad.ingest.settings import get_ingest_settings
from sanad.ingest.worker import NOTIFY_CHANNEL
from sanad.text.arabic import normalize_for_search

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

Editor = Annotated[User, Depends(require_role(Role.EDITOR, Role.ADMIN))]
_COPY_CHUNK = 1024 * 1024
_MAX_TITLE = 300
_MAX_TAGS = 20
_MAX_TAG = 50


# --- schemas -----------------------------------------------------------------------------------


class Uploader(BaseModel):
    id: uuid.UUID
    name: str


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    original_filename: str
    file_type: FileType
    # DOCX and TXT are shown as a PDF rendition whose page numbers may differ from Word's.
    is_converted: bool
    category: DocCategory | None
    year: int | None
    programme_id: uuid.UUID | None
    uploaded_by: Uploader
    uploaded_at: datetime
    page_count: int | None
    status: DocStatus
    language: DocLanguage | None
    error_code: str | None
    error_params: dict[str, Any] | None
    size_bytes: int
    tags: list[str]
    is_archived: bool
    restricted: bool
    is_seed: bool
    ready_at: datetime | None


class DocumentList(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int


class DocumentPatch(BaseModel):
    """Only the fields sent are changed; send null to clear category, year or programme."""

    title: str | None = Field(default=None, min_length=1, max_length=_MAX_TITLE)
    category: DocCategory | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    programme_id: uuid.UUID | None = None
    tags: list[Annotated[str, Field(min_length=1, max_length=_MAX_TAG)]] | None = Field(
        default=None, max_length=_MAX_TAGS
    )
    restricted: bool | None = None


class PageChunk(BaseModel):
    chunk_id: uuid.UUID
    chunk_index: int
    char_start: int
    char_end: int


class PageOut(BaseModel):
    document_id: uuid.UUID
    page_number: int
    page_count: int
    text: str
    char_count: int
    chunks: list[PageChunk]


# --- helpers -----------------------------------------------------------------------------------


def _out(document: Document, uploader_name: str) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        title=document.title,
        original_filename=document.original_filename,
        file_type=document.file_type,
        is_converted=document.is_converted,
        category=document.category,
        year=document.year,
        programme_id=document.programme_id,
        uploaded_by=Uploader(id=document.uploaded_by, name=uploader_name),
        uploaded_at=document.uploaded_at,
        page_count=document.page_count,
        status=document.status,
        language=document.language,
        error_code=document.error_code,
        error_params=document.error_params,
        size_bytes=document.size_bytes,
        tags=document.tags,
        is_archived=document.is_archived,
        restricted=document.restricted,
        is_seed=document.is_seed,
        ready_at=document.ready_at,
    )


def _with_uploader() -> Select[Document, str]:
    return select(Document, User.name).join(User, User.id == Document.uploaded_by)


async def _get_visible(
    db: AsyncSession, user: User, document_id: uuid.UUID, *, lock: bool = False
) -> tuple[Document, str]:
    """The document if `user` may see it (archived included: old citations still open)."""
    query = _with_uploader().where(
        Document.id == document_id, visible_documents(user, include_archived=True)
    )
    if lock:
        query = query.with_for_update(of=Document)
    row = (await db.execute(query)).one_or_none()
    if row is None:
        raise ApiError(404, ErrorCode.NOT_FOUND)
    document, uploader = row
    return document, uploader


async def _check_programme(db: AsyncSession, programme_id: uuid.UUID | None) -> None:
    if programme_id is not None and await db.get(Programme, programme_id) is None:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, fields=["programme_id"])


def _duplicate(existing_id: uuid.UUID) -> ApiError:
    return ApiError(409, ErrorCode.DUPLICATE_DOCUMENT, document_id=str(existing_id))


async def _notify_worker(db: AsyncSession) -> None:
    # Delivered when the transaction commits; wakes the worker at once.
    await db.execute(text(f"NOTIFY {NOTIFY_CHANNEL}"))


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _clean_tags(tags: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for tag in tags:
        tag = " ".join(tag.split())
        if tag:
            seen.setdefault(tag, None)
    return list(seen)


# --- upload ------------------------------------------------------------------------------------


def _spool(source: BinaryIO, incoming: Path, limit: int) -> tuple[Path, str, int]:
    """Copy the upload to a temporary file under FILES_DIR, hashing it, refusing it once it
    passes `limit` bytes. Runs in a worker thread (blocking file I/O)."""
    incoming.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=incoming)
    path = Path(name)
    digest = hashlib.sha256()
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := source.read(_COPY_CHUNK):
                size += len(chunk)
                if size > limit:
                    raise ApiError(413, ErrorCode.FILE_TOO_LARGE, max_bytes=limit)
                digest.update(chunk)
                out.write(chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path, digest.hexdigest(), size


def _keep(spooled: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(spooled, dest)


def _discard(spooled: Path) -> None:
    spooled.unlink(missing_ok=True)


@router.post("/documents", status_code=201, response_model=DocumentOut)
async def upload_document(
    user: Editor,
    db: DbSession,
    file: Annotated[UploadFile, File(description="One PDF, DOCX or TXT file")],
    title: Annotated[str | None, Form(max_length=_MAX_TITLE)] = None,
    category: Annotated[DocCategory | None, Form()] = None,
    year: Annotated[int | None, Form(ge=1900, le=2100)] = None,
    programme_id: Annotated[uuid.UUID | None, Form()] = None,
    restricted: Annotated[bool, Form()] = False,
    tags: Annotated[list[str] | None, Form()] = None,
) -> DocumentOut:
    """Upload one file. It is checked by content as well as extension, stored under a
    generated name, and queued for the worker."""
    settings = get_ingest_settings()
    filename = Path(file.filename or "").name
    try:
        file_type = type_from_name(filename)
    except IngestionError as exc:
        raise ApiError(415, exc.code) from None
    await _check_programme(db, programme_id)

    tmp_path, sha256, size = await run_in_threadpool(
        _spool, file.file, settings.files_dir / "incoming", settings.upload_max_bytes
    )
    try:
        try:
            await run_in_threadpool(check_content, tmp_path, file_type)
        except IngestionError as exc:
            if exc.code is ErrorCode.UNSUPPORTED_TYPE:
                raise ApiError(415, exc.code) from None
            # A damaged file (FILE_CORRUPT, TXT_ENCODING_UNKNOWN) is accepted and fails in the
            # worker, so it gets a Library row with a readable reason like any other bad file.
        existing = await db.scalar(
            select(Document.id).where(Document.sha256 == sha256, Document.is_archived.is_(False))
        )
        if existing is not None:
            raise _duplicate(existing)

        document_id = uuid.uuid4()
        stored = original_path(document_id, file_type)
        clean_title = " ".join((title or Path(filename).stem).split())[:_MAX_TITLE] or filename
        document = Document(
            id=document_id,
            title=clean_title,
            title_norm=normalize_for_search(clean_title),
            original_filename=filename,
            file_path=stored,
            file_type=file_type,
            category=category,
            year=year,
            programme_id=programme_id,
            uploaded_by=user.id,
            status=DocStatus.QUEUED,
            sha256=sha256,
            size_bytes=size,
            tags=_clean_tags(tags or []),
            restricted=restricted,
        )
        db.add(document)
        audit.record(
            db,
            "document.upload",
            actor_id=user.id,
            target_type="document",
            target_id=document_id,
            file_type=file_type.value,
            size_bytes=size,
            restricted=restricted,
        )
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            existing = await db.scalar(
                select(Document.id).where(
                    Document.sha256 == sha256, Document.is_archived.is_(False)
                )
            )
            raise _duplicate(existing or document_id) from None
        await run_in_threadpool(_keep, tmp_path, resolve(settings.files_dir, stored))
        await _notify_worker(db)
        await db.commit()
    except BaseException:
        await run_in_threadpool(_discard, tmp_path)
        raise
    await db.refresh(document)
    logger.info("document uploaded: %s (%s, %d bytes)", document_id, file_type.value, size)
    return _out(document, user.name)


# --- reads -------------------------------------------------------------------------------------

SortKey = Literal["uploaded_at", "-uploaded_at", "title", "-title", "year", "-year"]
_SORTS: dict[str, ColumnElement[Any]] = {
    "uploaded_at": Document.uploaded_at.asc(),
    "-uploaded_at": Document.uploaded_at.desc(),
    "title": Document.title_norm.asc(),
    "-title": Document.title_norm.desc(),
    "year": Document.year.asc().nulls_last(),
    "-year": Document.year.desc().nulls_last(),
}


@router.get("/documents", response_model=DocumentList)
async def list_documents(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=200, description="Title search")] = None,
    file_type: Annotated[list[FileType] | None, Query()] = None,
    category: Annotated[list[DocCategory] | None, Query()] = None,
    uncategorised: Annotated[bool, Query(description="Only documents with no category")] = False,
    year: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    year_from: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    year_to: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    programme_id: Annotated[list[uuid.UUID] | None, Query()] = None,
    status: Annotated[list[DocStatus] | None, Query()] = None,
    restricted: Annotated[bool | None, Query()] = None,
    include_archived: Annotated[bool, Query()] = False,
    ids: Annotated[list[uuid.UUID] | None, Query(max_length=100)] = None,
    sort: Annotated[SortKey, Query()] = "-uploaded_at",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> DocumentList:
    """The Library. Filters combine with AND; list-valued filters match any of their values.
    `ids` serves the upload screen's status polling (archived ones included)."""
    conditions = [visible_documents(user, include_archived=include_archived or bool(ids))]
    if q and (term := normalize_for_search(q).strip()):
        conditions.append(Document.title_norm.like(_like(term), escape="\\"))
    if file_type:
        conditions.append(Document.file_type.in_(file_type))
    if category or uncategorised:
        options = [Document.category.in_(category)] if category else []
        if uncategorised:
            options.append(Document.category.is_(None))
        conditions.append(or_(*options))
    if year is not None:
        conditions.append(Document.year == year)
    if year_from is not None:
        conditions.append(Document.year >= year_from)
    if year_to is not None:
        conditions.append(Document.year <= year_to)
    if programme_id:
        conditions.append(Document.programme_id.in_(programme_id))
    if status:
        conditions.append(Document.status.in_(status))
    if restricted is not None and can_see_restricted(user):
        conditions.append(Document.restricted.is_(restricted))
    if ids:
        conditions.append(Document.id.in_(ids))
    where = and_(*conditions)

    total = await db.scalar(select(func.count()).select_from(Document).where(where)) or 0
    rows = await db.execute(
        _with_uploader()
        .where(where)
        .order_by(_SORTS[sort], Document.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return DocumentList(
        items=[_out(document, name) for document, name in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(document_id: uuid.UUID, user: CurrentUser, db: DbSession) -> DocumentOut:
    document, uploader = await _get_visible(db, user, document_id)
    return _out(document, uploader)


@router.get(
    "/documents/{document_id}/file",
    response_class=FileResponse,
    responses={200: {"content": {"application/pdf": {}}, "description": "The viewer PDF"}},
)
async def get_document_file(document_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    """The PDF the viewer shows (for DOCX and TXT, the LibreOffice rendition). Page numbers
    in citations refer to this file."""
    document, _ = await _get_visible(db, user, document_id)
    if document.viewer_path is None:
        raise ApiError(409, ErrorCode.DOCUMENT_NOT_READY)
    path = resolve(get_ingest_settings().files_dir, document.viewer_path)
    if not path.is_file():
        raise ApiError(409, ErrorCode.DOCUMENT_NOT_READY)
    return FileResponse(
        path,
        media_type="application/pdf",
        content_disposition_type="inline",
        filename=f"{document.id}.pdf",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/documents/{document_id}/pages/{page_number}", response_model=PageOut)
async def get_document_page(
    document_id: uuid.UUID,
    page_number: Annotated[int, PathParam(ge=1)],
    user: CurrentUser,
    db: DbSession,
) -> PageOut:
    """Cleaned text of one viewer page, with the spans of the chunks cut from it."""
    document, _ = await _get_visible(db, user, document_id)
    if document.page_count is None:
        raise ApiError(409, ErrorCode.DOCUMENT_NOT_READY)
    page = await db.get(DocumentPage, (document_id, page_number))
    if page is None:
        raise ApiError(404, ErrorCode.NOT_FOUND)
    chunks = await db.execute(
        select(Chunk.id, Chunk.chunk_index, Chunk.char_start, Chunk.char_end)
        .where(
            Chunk.document_id == document_id,
            Chunk.page_number == page_number,
            Chunk.index_generation == ACTIVE_INDEX_GENERATION,
        )
        .order_by(Chunk.chunk_index)
    )
    return PageOut(
        document_id=document_id,
        page_number=page_number,
        page_count=document.page_count,
        text=page.text,
        char_count=page.char_count,
        chunks=[
            PageChunk(
                chunk_id=c.id,
                chunk_index=c.chunk_index,
                char_start=c.char_start,
                char_end=c.char_end,
            )
            for c in chunks
        ],
    )


# --- metadata and lifecycle --------------------------------------------------------------------


@router.patch("/documents/{document_id}", response_model=DocumentOut)
async def update_document(
    document_id: uuid.UUID, body: DocumentPatch, user: Editor, db: DbSession
) -> DocumentOut:
    document, uploader = await _get_visible(db, user, document_id, lock=True)
    changes = body.model_dump(exclude_unset=True)
    if "title" in changes and changes["title"] is None:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, fields=["title"])
    if "restricted" in changes and changes["restricted"] is None:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, fields=["restricted"])
    if "programme_id" in changes:
        await _check_programme(db, changes["programme_id"])
    if "title" in changes:
        changes["title"] = " ".join(changes["title"].split()) or document.title
        changes["title_norm"] = normalize_for_search(changes["title"])
    if "tags" in changes:
        changes["tags"] = _clean_tags(changes["tags"] or [])
    for field, value in changes.items():
        setattr(document, field, value)
    audit.record(
        db,
        "document.update",
        actor_id=user.id,
        target_type="document",
        target_id=document_id,
        fields=sorted(body.model_fields_set),
    )
    await db.commit()
    await db.refresh(document)
    return _out(document, uploader)


@router.post("/documents/{document_id}/archive", response_model=DocumentOut)
async def archive_document(document_id: uuid.UUID, user: Editor, db: DbSession) -> DocumentOut:
    """Out of the Library and retrieval; still reachable by id, so old citations open."""
    document, uploader = await _get_visible(db, user, document_id, lock=True)
    if not document.is_archived:
        document.is_archived = True
        document.archived_at = datetime.now(UTC)
        document.archived_by = user.id
        audit.record(
            db, "document.archive", actor_id=user.id, target_type="document", target_id=document_id
        )
        await db.commit()
        await db.refresh(document)
    return _out(document, uploader)


@router.post("/documents/{document_id}/unarchive", response_model=DocumentOut)
async def unarchive_document(document_id: uuid.UUID, user: Editor, db: DbSession) -> DocumentOut:
    document, uploader = await _get_visible(db, user, document_id, lock=True)
    if document.is_archived:
        existing = await db.scalar(
            select(Document.id).where(
                Document.sha256 == document.sha256, Document.is_archived.is_(False)
            )
        )
        if existing is not None:
            raise _duplicate(existing)
        document.is_archived = False
        document.archived_at = None
        document.archived_by = None
        audit.record(
            db,
            "document.unarchive",
            actor_id=user.id,
            target_type="document",
            target_id=document_id,
        )
        await db.commit()
        await db.refresh(document)
    return _out(document, uploader)


@router.post("/documents/{document_id}/retry", response_model=DocumentOut)
async def retry_document(document_id: uuid.UUID, user: Editor, db: DbSession) -> DocumentOut:
    """Queue a failed document again, with a fresh set of attempts."""
    document, uploader = await _get_visible(db, user, document_id, lock=True)
    if document.status is not DocStatus.FAILED:
        raise ApiError(409, ErrorCode.DOCUMENT_NOT_RETRYABLE)
    document.status = DocStatus.QUEUED
    document.error_code = None
    document.error_params = None
    document.attempts = 0
    document.processing_started_at = None
    audit.record(
        db, "document.retry", actor_id=user.id, target_type="document", target_id=document_id
    )
    await _notify_worker(db)
    await db.commit()
    await db.refresh(document)
    return _out(document, uploader)
