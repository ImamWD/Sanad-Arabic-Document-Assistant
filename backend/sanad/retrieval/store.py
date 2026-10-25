"""Storing questions and reading them back (history), plus the speed samples behind the ETA.

The guest is one shared account, so its history is scoped to the current session: a second
guest login sees none of the first session's questions (ROADMAP R1).
"""

import uuid
from typing import Any

from sqlalchemy import Select, false, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from sanad.core.models import User
from sanad.documents.access import visible_documents
from sanad.documents.models import Chunk, Document
from sanad.llm.eta import PerfSample
from sanad.retrieval.models import Citation, LlmPerfSample, Query
from sanad.retrieval.pipeline import snippet
from sanad.retrieval.types import Outcome, QueryRecord


class SqlQueryStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def recent_perf(self, llm_model: str, limit: int) -> list[PerfSample]:
        async with AsyncSession(self._engine) as db:
            rows = await db.scalars(
                select(LlmPerfSample)
                .where(LlmPerfSample.llm_model == llm_model)
                .order_by(LlmPerfSample.created_at.desc(), LlmPerfSample.id.desc())
                .limit(limit)
            )
            return [
                PerfSample(r.prompt_chars, r.prompt_ms, r.output_ms, r.output_tokens) for r in rows
            ]

    async def save(self, record: QueryRecord) -> uuid.UUID:
        query = Query(
            user_id=record.user_id,
            session_id=record.session_id,
            question=record.question,
            answer=record.answer,
            language=record.language,
            outcome=record.outcome,
            band=record.band,
            refusal_reason=record.refusal_reason,
            error_code=record.error_code,
            top_score=record.top_score,
            filters=record.filters,
            nearest_document_ids=record.nearest_document_ids,
            llm_provider=record.llm_provider,
            llm_model=record.llm_model,
            latency_ms=record.latency_ms,
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
        )
        async with AsyncSession(self._engine, expire_on_commit=False) as db:
            db.add(query)
            await db.flush()
            db.add_all(
                Citation(query_id=query.id, chunk_id=c.chunk_id, rank=c.rank, score=c.score)
                for c in record.citations
            )
            if record.perf is not None and record.llm_provider and record.llm_model:
                db.add(
                    LlmPerfSample(
                        llm_provider=record.llm_provider,
                        llm_model=record.llm_model,
                        prompt_chars=record.perf.prompt_chars,
                        prompt_tokens=record.perf.prompt_tokens,
                        prompt_ms=record.perf.prompt_ms,
                        output_tokens=record.perf.output_tokens,
                        output_ms=record.perf.output_ms,
                    )
                )
            await db.commit()
        return query.id


def own_queries(user: User, session_id: str | None) -> Select[Query]:
    """The user's own questions; for the guest, only those of the current session. Errors
    (no answer could run) are not part of the history."""
    stmt = select(Query).where(Query.user_id == user.id, Query.outcome != Outcome.ERROR)
    if user.is_guest:
        stmt = stmt.where(Query.session_id == session_id) if session_id else stmt.where(false())
    return stmt


async def history(db: AsyncSession, user: User, session_id: str | None, limit: int) -> list[Query]:
    stmt = own_queries(user, session_id).order_by(Query.created_at.desc(), Query.id).limit(limit)
    return list((await db.scalars(stmt)).all())


async def stored_answer(
    db: AsyncSession, user: User, session_id: str | None, query_id: uuid.UUID, snippet_chars: int
) -> dict[str, Any] | None:
    """One of the user's questions with its answer, in the shape of the `final` event plus
    `question` and `created_at`; None if it isn't theirs to see. Citations and suggested titles
    are re-checked against what the user may see now."""
    query = await db.scalar(own_queries(user, session_id).where(Query.id == query_id))
    if query is None:
        return None
    visible = visible_documents(user, include_archived=True)
    citations = (
        await db.execute(
            select(Citation, Chunk, Document)
            .join(Chunk, Chunk.id == Citation.chunk_id)
            .join(Document, Document.id == Chunk.document_id)
            .where(Citation.query_id == query.id, visible)
            .order_by(Citation.rank)
        )
    ).all()
    nearest_rows = (
        await db.execute(
            select(Document.id, Document.title).where(
                Document.id.in_(query.nearest_document_ids), visible
            )
        )
    ).all()
    titles = dict(nearest_rows)
    return {
        "query_id": str(query.id),
        "question": query.question,
        "created_at": query.created_at.isoformat(),
        "outcome": query.outcome.value,
        "band": query.band.value if query.band else None,
        "refusal_reason": query.refusal_reason.value if query.refusal_reason else None,
        "answer": query.answer,
        "citations": [
            {
                "rank": citation.rank,
                "document_id": str(doc.id),
                "title": doc.title,
                "page_number": chunk.page_number,
                "snippet": snippet(chunk.text, snippet_chars),
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "file_type": doc.file_type.value,
                "is_converted": doc.is_converted,
            }
            for citation, chunk, doc in citations
        ],
        "nearest_documents": [
            {"document_id": str(doc_id), "title": titles[doc_id]}
            for doc_id in query.nearest_document_ids
            if doc_id in titles
        ],
    }
