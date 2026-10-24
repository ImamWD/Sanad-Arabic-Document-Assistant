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


class AskResult(BaseModel):
    """`POST /ask`, and the `final` event of `POST /ask/stream`. `answer` is null exactly when
    the outcome is no_answer: streamed text is never kept as the answer."""

    query_id: uuid.UUID
    outcome: Outcome
    band: Band | None
    refusal_reason: RefusalReason | None
    answer: str | None
    citations: list[CitationOut]
    nearest_documents: list[NearestDocumentOut]


class StoredAnswer(AskResult):
    """`GET /queries/{id}`: a stored question with its validated answer."""

    question: str
    created_at: datetime
