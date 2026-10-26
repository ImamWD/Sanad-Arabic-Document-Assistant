"""Hybrid retrieval over the chunks a user may read (SYSTEM_DESIGN §6).

dense (pgvector, cosine) and lexical (tsvector, an OR of content terms) -> reciprocal-rank
fusion -> rerank through the ml service.

Every query here goes through `retrievable_chunks(user)` (B3's `visible_documents` rule plus
ready, not archived, active index): Viewers and the guest never retrieve a restricted document,
and the guest retrieves seed documents only. A restricted document can't reach a Viewer's
answer, cited or not, because it never reaches the prompt.
"""

import time
import uuid
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, exists, func, literal_column, select, text, true
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.sql.elements import ColumnClause

from sanad.core.models import Programme, User
from sanad.documents.access import retrievable_chunks
from sanad.documents.models import Chunk, DocLanguage, Document
from sanad.retrieval.fuse import rrf
from sanad.retrieval.ml import AskMl
from sanad.retrieval.programmes import ProgrammeName, named_programmes, rerank_query
from sanad.retrieval.settings import RetrievalSettings
from sanad.retrieval.types import Candidate, Filters, Retrieved
from sanad.text.arabic import lexical_terms, strip_marks

MAX_LEXICAL_TERMS = 32
_SIMPLE: ColumnClause[Any] = literal_column("'simple'::regconfig")


def scope(user: User, filters: Filters) -> ColumnElement[bool]:
    """What `user` may retrieve, narrowed by the optional filters. Needs Chunk joined to
    Document."""
    clauses = [retrievable_chunks(user)]
    if filters.programme_id is not None:
        clauses.append(Document.programme_id == filters.programme_id)
    if filters.year_from is not None:
        clauses.append(Document.year >= filters.year_from)
    if filters.year_to is not None:
        clauses.append(Document.year <= filters.year_to)
    if filters.category is not None:
        clauses.append(Document.category == filters.category)
    return and_(true(), *clauses)


def _chunks(user: User, filters: Filters) -> Select[uuid.UUID]:
    return (
        select(Chunk.id)
        .join(Document, Document.id == Chunk.document_id)
        .where(scope(user, filters))
    )


def lexical_query(question: str) -> ColumnElement[str] | None:
    """An OR of `phraseto_tsquery('simple', term)` over the question's content terms (B1's
    `lexical_terms`, normalised like `chunks.text_norm`). Never `plainto_tsquery` on the raw
    question: it ANDs every word, so a natural Arabic question would match almost nothing.
    One phrase query per term keeps codes such as `yep-2021-03` together."""
    terms = lexical_terms(question)[:MAX_LEXICAL_TERMS]
    query: ColumnElement[str] | None = None
    for term in terms:
        part = func.phraseto_tsquery(_SIMPLE, term)
        query = part if query is None else query.op("||")(part)
    return query


async def dense_ids(
    db: AsyncSession, user: User, filters: Filters, vector: Sequence[float], limit: int
) -> list[uuid.UUID]:
    # Exact order through the HNSW index even when the access filter drops many neighbours.
    await db.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
    stmt = (
        _chunks(user, filters)
        .order_by(Chunk.embedding.cosine_distance(list(vector)), Chunk.id)
        .limit(limit)
    )
    return list((await db.scalars(stmt)).all())


async def lexical_ids(
    db: AsyncSession, user: User, filters: Filters, question: str, limit: int
) -> list[uuid.UUID]:
    query = lexical_query(question)
    if query is None:
        return []
    stmt = (
        _chunks(user, filters)
        .where(Chunk.tsv.op("@@")(query))
        .order_by(func.ts_rank_cd(Chunk.tsv, query).desc(), Chunk.id)
        .limit(limit)
    )
    return list((await db.scalars(stmt)).all())


async def load_candidates(
    db: AsyncSession, user: User, filters: Filters, ids: Sequence[uuid.UUID]
) -> list[Candidate]:
    """The chunks behind `ids`, in that order (re-checked against the user's scope)."""
    if not ids:
        return []
    stmt = (
        select(Chunk, Document, Programme.name_ar, Programme.name_en)
        .join(Document, Document.id == Chunk.document_id)
        .outerjoin(Programme, Programme.id == Document.programme_id)
        .where(scope(user, filters), Chunk.id.in_(ids))
    )
    rows = {row[0].id: row for row in (await db.execute(stmt)).all()}
    candidates = []
    for chunk_id in ids:
        if chunk_id not in rows:
            continue
        chunk, doc, name_ar, name_en = rows[chunk_id]
        candidates.append(
            Candidate(
                chunk_id=chunk.id,
                document_id=doc.id,
                title=doc.title,
                page_number=chunk.page_number,
                text=chunk.text,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                file_type=doc.file_type.value,
                is_converted=doc.is_converted,
                is_seed=doc.is_seed,
                language=doc.language.value if doc.language else None,
                score=0.0,
                file=doc.original_filename,
                programme=name_en if doc.language is DocLanguage.EN else name_ar,
                year=doc.year,
            )
        )
    return candidates


def rerank_passage(candidate: Candidate) -> str:
    """The title goes with the text: a budget table row rarely names its programme, and the
    title tells two donor agreements' identical rows apart."""
    return f"{candidate.title}\n{candidate.text}"


class SqlRetriever:
    def __init__(self, engine: AsyncEngine, ml: AskMl, settings: RetrievalSettings) -> None:
        self._engine = engine
        self._ml = ml
        self._settings = settings

    async def retrieve(self, user: User, question: str, filters: Filters) -> Retrieved:
        """The embedding and the reranker get the question without tashkeel or tatweel: the
        documents are written without them, and a fully diacritised question otherwise looks
        unlike every passage. The word search normalises on its own; the model still gets the
        question as asked.

        When the question names a programme by its distinctive words («نظام الصحة المجتمعية»),
        the reranker also gets the programme's official names (sanad.retrieval.programmes)."""
        s = self._settings
        plain = strip_marks(question)
        watch = _Laps()
        async with AsyncSession(self._engine) as db:
            # Nothing to search (an empty library, or filters that exclude everything): a gate
            # refusal, without waking the ml service.
            if not await db.scalar(select(exists(_chunks(user, filters)))):
                return Retrieved([])
            vector = await self._ml.embed(plain)
            watch.lap("embed")
            dense = await dense_ids(db, user, filters, vector, s.dense_candidates)
            lexical = await lexical_ids(db, user, filters, question, s.lexical_candidates)
            fused = rrf([dense, lexical], k=s.rrf_k, limit=s.rerank_candidates)
            candidates = await load_candidates(db, user, filters, fused)
            programmes = [
                ProgrammeName(name_ar, name_en)
                for name_ar, name_en in await db.execute(
                    select(Programme.name_ar, Programme.name_en)
                    .where(Programme.is_active)
                    .order_by(Programme.code)
                )
            ]
            watch.lap("retrieve")
        query = rerank_query(plain, named_programmes(plain, programmes))
        scores = await self._ml.rerank(query, [rerank_passage(c) for c in candidates])
        watch.lap("rerank")
        dense_rank = {chunk_id: n for n, chunk_id in enumerate(dense, start=1)}
        lexical_rank = {chunk_id: n for n, chunk_id in enumerate(lexical, start=1)}
        ranked = sorted(
            (
                replace(
                    c,
                    score=score,
                    dense_rank=dense_rank.get(c.chunk_id),
                    lexical_rank=lexical_rank.get(c.chunk_id),
                )
                for c, score in zip(candidates, scores, strict=True)
            ),
            key=lambda c: -c.score,
        )
        return Retrieved(ranked, watch.laps)


class _Laps:
    """Milliseconds per named step, each measured from the end of the previous one."""

    def __init__(self) -> None:
        self._last = time.monotonic()
        self.laps: dict[str, int] = {}

    def lap(self, name: str) -> None:
        now = time.monotonic()
        self.laps[name] = round((now - self._last) * 1000)
        self._last = now
