"""ORM models for questions, their citations and measured LLM speed (revision 0003_queries).

The Postgres enum types are created by the migration, never by the ORM (`create_type=False`).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import REAL, BigInteger, DateTime, ForeignKey, Identity, Integer, SmallInteger, Text
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from sanad.core.models import LANGUAGE_ENUM, Base, Language
from sanad.llm.validate import RefusalReason
from sanad.retrieval.gate import Band
from sanad.retrieval.types import Outcome


def _pg_enum(enum: type[StrEnum], name: str) -> ENUM:
    return ENUM(
        enum,
        name=name,
        values_callable=lambda members: [m.value for m in members],
        create_type=False,
        validate_strings=True,
    )


OUTCOME_ENUM = _pg_enum(Outcome, "answer_outcome")
BAND_ENUM = _pg_enum(Band, "answer_band")
REFUSAL_REASON_ENUM = _pg_enum(RefusalReason, "refusal_reason")

_NOW = sql("now()")


class Query(Base):
    __tablename__ = "queries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    session_id: Mapped[str | None] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    language: Mapped[Language] = mapped_column(LANGUAGE_ENUM)
    outcome: Mapped[Outcome] = mapped_column(OUTCOME_ENUM)
    band: Mapped[Band | None] = mapped_column(BAND_ENUM)
    refusal_reason: Mapped[RefusalReason | None] = mapped_column(REFUSAL_REASON_ENUM)
    error_code: Mapped[str | None] = mapped_column(Text)
    top_score: Mapped[float | None] = mapped_column(REAL)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sql("'{}'::jsonb"))
    nearest_document_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), server_default=sql("'{}'::uuid[]")
    )
    llm_provider: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql("gen_random_uuid()"),
    )
    query_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("queries.id", ondelete="CASCADE"))
    chunk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chunks.id"))
    rank: Mapped[int] = mapped_column(SmallInteger)
    score: Mapped[float | None] = mapped_column(REAL)


class LlmPerfSample(Base):
    __tablename__ = "llm_perf_samples"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    llm_provider: Mapped[str] = mapped_column(Text)
    llm_model: Mapped[str] = mapped_column(Text)
    prompt_chars: Mapped[int] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    prompt_ms: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    output_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
