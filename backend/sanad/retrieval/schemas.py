"""Response shapes of the ask routes (the OpenAPI contract the Ask screen codes against)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from sanad.llm.validate import RefusalReason
from sanad.retrieval.gate import Band
from sanad.retrieval.types import Outcome


class CitationOut(BaseModel):
    rank: int  # the [n] marker in the answer
    document_id: uuid.UUID
    title: str
    page_number: int  # a page of the viewer PDF (for DOCX and TXT, the converted rendition)
    snippet: str
    char_start: int
    char_end: int
    file_type: str
    is_converted: bool


class NearestDocumentOut(BaseModel):
    document_id: uuid.UUID
    title: str


class DiagnosticCandidate(BaseModel):
    rank: int  # 1 = the best reranked candidate
    document_id: uuid.UUID
    file: str  # the document's original file name (for seed documents, the manifest `file`)
    page_number: int
    chunk_id: uuid.UUID
    rerank_score: float
    dense_rank: int | None  # place in the vector search, if it was in the top DENSE_CANDIDATES
    lexical_rank: int | None  # place in the word search, if it was in the top LEXICAL_CANDIDATES


class DiagnosticTimings(BaseModel):
    """Milliseconds. `first_token` and `generate` are null when the LLM wasn't called."""

    embed: int | None
    retrieve: int | None
    rerank: int | None
    first_token: int | None
    generate: int | None
    total: int


class Diagnostics(BaseModel):
    """Retrieval and timing for the eval (E1). Ids, positions and scores only, never text."""

    candidates: list[DiagnosticCandidate]
    top_score: float | None
    band: Band
    timings_ms: DiagnosticTimings
    llm_model: str


class AnswerFields(BaseModel):
    query_id: uuid.UUID
    outcome: Outcome
    band: Band | None
    refusal_reason: RefusalReason | None
    answer: str | None
    citations: list[CitationOut]
    nearest_documents: list[NearestDocumentOut]


class AskResult(AnswerFields):
    """`POST /ask`, and the `final` event of `POST /ask/stream`. `answer` is null exactly when
    the outcome is no_answer: streamed text is never kept as the answer. `diagnostics` is there
    only when an editor or admin asked for it with `debug` (and ASK_DEBUG_ENABLED is on)."""

    diagnostics: Diagnostics | None = None


class StoredAnswer(AnswerFields):
    """`GET /queries/{id}`: a stored question with its validated answer."""

    question: str
    created_at: datetime
