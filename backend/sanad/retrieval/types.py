"""Values passed between retrieval, the pipeline and the query store."""

import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from sanad.core.models import User
from sanad.llm.eta import PerfSample
from sanad.llm.validate import RefusalReason
from sanad.retrieval.gate import Band


class Outcome(StrEnum):
    ANSWERED = "answered"
    LOW_CONFIDENCE = "low_confidence"
    NO_ANSWER = "no_answer"
    ERROR = "error"


@dataclass(frozen=True)
class Filters:
    """Optional narrowing of the retrieval scope (SYSTEM_DESIGN §6)."""

    programme_id: uuid.UUID | None = None
    year_from: int | None = None
    year_to: int | None = None
    category: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {k: str(v) if isinstance(v, uuid.UUID) else v for k, v in asdict(self).items() if v}


@dataclass(frozen=True)
class Candidate:
    """A retrieved chunk with what the prompt, the citation card and the guard need."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    page_number: int
    text: str
    char_start: int
    char_end: int
    file_type: str
    is_converted: bool
    is_seed: bool
    language: str | None
    score: float  # reranker score, 0..1
    # For the eval's diagnostics (E1): the document's file name (for seed documents, the
    # manifest `file` the eval sets cite) and the chunk's place in each first-stage ranking.
    file: str = ""
    dense_rank: int | None = None
    lexical_rank: int | None = None


@dataclass(frozen=True)
class Retrieved:
    candidates: list[Candidate]  # best reranked first
    # Milliseconds spent embedding the question, in the dense and lexical queries, reranking.
    timings_ms: dict[str, int] = field(default_factory=dict)

    @property
    def top_score(self) -> float | None:
        return self.candidates[0].score if self.candidates else None


class Retriever(Protocol):
    async def retrieve(self, user: User, question: str, filters: Filters) -> Retrieved:
        """Hybrid search plus rerank, only over what `user` may retrieve. Raises
        `MlUnavailableError` when the ml service can't embed or rerank."""
        ...


@dataclass(frozen=True)
class PerfRecord:
    prompt_chars: int
    prompt_tokens: int | None
    prompt_ms: int
    output_tokens: int | None
    output_ms: int


@dataclass(frozen=True)
class CitationRecord:
    rank: int
    chunk_id: uuid.UUID
    score: float


@dataclass(frozen=True)
class QueryRecord:
    """One row of `queries`, its citations, and (after a generation) a speed sample."""

    user_id: uuid.UUID
    session_id: str | None
    question: str
    language: str
    outcome: Outcome
    band: Band | None
    refusal_reason: RefusalReason | None
    answer: str | None
    top_score: float | None
    filters: dict[str, Any]
    latency_ms: int
    error_code: str | None = None
    nearest_document_ids: list[uuid.UUID] = field(default_factory=list)
    llm_provider: str | None = None
    llm_model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    citations: list[CitationRecord] = field(default_factory=list)
    perf: PerfRecord | None = None


class QueryStore(Protocol):
    async def recent_perf(self, llm_model: str, limit: int) -> list[PerfSample]:
        """This machine's most recent measured generations for the model."""
        ...

    async def save(self, record: QueryRecord) -> uuid.UUID:
        """Store the query (and its citations and speed sample); return its id."""
        ...
