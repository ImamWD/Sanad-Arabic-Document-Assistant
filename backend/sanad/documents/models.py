"""ORM models for documents, their pages and their chunks (Alembic revision 0002_documents).

The Postgres enum types and the pgvector extension are created by the migration, never by
the ORM (`create_type=False`).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from sanad.core.models import DOC_CATEGORY_ENUM, Base, DocCategory
from sanad.ingest.filetypes import FileType

EMBEDDING_DIM = 1024  # BAAI/bge-m3 (DECISIONS D2)
# Chunks are written into this generation; retrieval reads it. Re-indexing (new chunk
# parameters or a new embedding model) will write the next one and switch over.
ACTIVE_INDEX_GENERATION = 1


class DocStatus(StrEnum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class DocLanguage(StrEnum):
    AR = "ar"
    EN = "en"
    MIXED = "mixed"


def _pg_enum(enum: type[StrEnum], name: str) -> ENUM:
    return ENUM(
        enum,
        name=name,
        values_callable=lambda members: [m.value for m in members],
        create_type=False,
        validate_strings=True,
    )


FILE_TYPE_ENUM = _pg_enum(FileType, "file_type")
DOC_STATUS_ENUM = _pg_enum(DocStatus, "doc_status")
DOC_LANGUAGE_ENUM = _pg_enum(DocLanguage, "doc_language")

_NOW = sql("now()")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    title: Mapped[str] = mapped_column(Text)
    title_norm: Mapped[str] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(Text)  # relative to FILES_DIR
    viewer_path: Mapped[str | None] = mapped_column(Text)  # relative to FILES_DIR
    file_type: Mapped[FileType] = mapped_column(FILE_TYPE_ENUM)
    category: Mapped[DocCategory | None] = mapped_column(DOC_CATEGORY_ENUM)
    year: Mapped[int | None] = mapped_column(SmallInteger)
    programme_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("programmes.id"))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    page_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[DocStatus] = mapped_column(DOC_STATUS_ENUM, server_default=DocStatus.QUEUED)
    language: Mapped[DocLanguage | None] = mapped_column(DOC_LANGUAGE_ENUM)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    attempts: Mapped[int] = mapped_column(Integer, server_default=sql("0"))
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sha256: Mapped[str] = mapped_column(CHAR(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sql("'{}'::text[]"))
    is_archived: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    restricted: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    is_seed: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=_NOW, onupdate=func.now()
    )

    @property
    def is_converted(self) -> bool:
        """DOCX and TXT are shown as LibreOffice PDFs: their page numbers can differ from
        Word's own paging, and citation cards say so (client review, BUILD_PLAN Part 2)."""
        return self.file_type is not FileType.PDF


class DocumentPage(Base):
    __tablename__ = "document_pages"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    page_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    text_norm: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer)


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "page_number"],
            ["document_pages.document_id", "document_pages.page_number"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    page_number: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    text_norm: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    token_count: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str] = mapped_column(Text)
    index_generation: Mapped[int] = mapped_column(
        Integer, server_default=sql(str(ACTIVE_INDEX_GENERATION))
    )
    tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', text_norm)", persisted=True)
    )
