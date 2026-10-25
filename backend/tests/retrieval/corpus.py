"""A small synthetic corpus for the DB-backed tests, with a deterministic fake ml service.

Texts and titles are taken from the synthetic seed corpus (seed/sources): the restricted
`wlp-donor-agreement-2022` page 3 holds the only "84,000" salary line, and two other donor
agreements carry the same «رواتب فريق المشروع» row with other figures.

The fake embedding is a hashed bag of normalised search tokens, so cosine similarity follows
word overlap; the fake reranker scores the share of the question's content terms found in the
passage. Both are crude but deterministic, which is all the access and flow tests need.
"""

import hashlib
import math
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import sqlalchemy
from sqlalchemy import insert, select

from sanad.core.models import Programme
from sanad.documents.models import Chunk, Document, DocumentPage
from sanad.text.arabic import lexical_terms, normalize_for_search, search_tokens

DIM = 1024
WLP_QUESTION = (
    "كم خُصّص لرواتب فريق المشروع في اتفاقية تمويل برنامج سبل العيش للنساء المعيلات لعام 2022؟"
)


def fake_embedding(text: str) -> list[float]:
    vector = [0.0] * DIM
    for token in search_tokens(text):
        vector[int(hashlib.sha256(token.encode()).hexdigest(), 16) % DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def fake_rerank_score(question: str, passage: str) -> float:
    terms = lexical_terms(question)
    if not terms:
        return 0.0
    tokens = set(search_tokens(passage))
    return sum(t in tokens for t in terms) / len(terms)


@dataclass
class FakeMl:
    embedded: list[str] = field(default_factory=list)
    reranked: list[list[str]] = field(default_factory=list)
    rerank_queries: list[str] = field(default_factory=list)

    async def embed(self, text: str) -> list[float]:
        self.embedded.append(text)
        return fake_embedding(text)

    async def rerank(self, query: str, passages: Sequence[str]) -> list[float]:
        self.reranked.append(list(passages))
        self.rerank_queries.append(query)
        return [fake_rerank_score(query, p) for p in passages]


@dataclass(frozen=True)
class Doc:
    slug: str
    title: str
    pages: dict[int, str]
    language: str = "ar"
    file_type: str = "pdf"
    restricted: bool = False
    is_seed: bool = True
    is_archived: bool = False
    status: str = "ready"
    year: int | None = None
    category: str | None = None
    programme: str | None = None  # programme code from seed/manifest.json


SEED_SOURCES = Path(__file__).resolve().parents[3] / "seed" / "sources"
_PAGE_MARK = re.compile(r"<!-- page (\d+) -->")


@cache
def _source_pages(slug: str) -> dict[int, str]:
    parts = _PAGE_MARK.split((SEED_SOURCES / f"{slug}.md").read_text(encoding="utf-8"))
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


def seed_pages(slug: str, *numbers: int) -> dict[int, str]:
    """Pages of a seed source, flattened roughly as extraction gives them (no markdown)."""
    pages = {}
    for number in numbers:
        lines = []
        for raw in _source_pages(slug)[number].splitlines():
            line = " ".join(raw.replace("|", " ").replace("**", "").lstrip("#>- ").split())
            if line and set(line) - set("-: "):
                lines.append(line)
        pages[number] = "\n".join(lines)
    return pages


CORPUS: list[Doc] = [
    Doc(
        "wlp-donor-agreement-2022",
        "اتفاقية تمويل المشروع WLP-2022-01 مع مؤسسة بيارق النور الخيرية",
        seed_pages("wlp-donor-agreement-2022", 1, 3),
        restricted=True,
        year=2022,
        category="donor_agreement",
        programme="WLP",
    ),
    Doc(
        "spc-donor-agreement-2023",
        "اتفاقية منحة المشروع SPC-2023-01 مع صندوق تلال العنبر للتنمية",
        seed_pages("spc-donor-agreement-2023", 3),
        file_type="docx",
        year=2023,
        category="donor_agreement",
        programme="SPC",
    ),
    Doc(
        "wash-donor-agreement-2018",
        "اتفاقية منحة المشروع WASH-2018-01 مع صندوق سدرة الوادي للتنمية",
        seed_pages("wash-donor-agreement-2018", 5),
        year=2018,
        category="donor_agreement",
        programme="WASH",
    ),
    Doc(
        "annual-report-2021",
        "التقرير السنوي 2021",
        seed_pages("annual-report-2021", 6),
        year=2021,
        category="annual_report",
    ),
    Doc(
        "annual-report-2023-en",
        "Annual Report 2023",
        seed_pages("annual-report-2023-en", 2),
        language="en",
        year=2023,
        category="annual_report",
    ),
    # Page 3 quotes an "ignore all previous instructions" message (the injection fixture).
    Doc(
        "spc-satisfaction-survey-2024",
        "مسح رضا المستفيدين من المشروع SPC-2023-01 لعام 2024",
        seed_pages("spc-satisfaction-survey-2024", 2, 3),
        file_type="txt",
        year=2024,
        category="field_survey",
    ),
    # Uploaded by staff, not part of the seed corpus: the guest must never retrieve it.
    Doc(
        "staff-memo",
        "مذكرة داخلية عن رواتب فريق المشروع",
        {1: "مذكرة داخلية: مراجعة رواتب فريق المشروع لعام 2025 قيد الإعداد."},
        is_seed=False,
        year=2025,
    ),
    # Archived and still indexing: nobody retrieves these.
    Doc(
        "budget-2024-draft",
        "مشروع الموازنة 2024",
        {2: "رواتب فريق المشروع في المسودة كما وردت قبل الاعتماد."},
        is_archived=True,
        year=2024,
        category="budget",
    ),
    Doc(
        "indexing-report",
        "تقرير قيد الفهرسة",
        {1: "رواتب فريق المشروع في تقرير لم تكتمل فهرسته."},
        status="indexing",
    ),
]


def insert_corpus(engine: sqlalchemy.Engine, uploaded_by: uuid.UUID) -> dict[str, uuid.UUID]:
    """Insert CORPUS (documents, pages, chunks with fake embeddings); return ids by slug."""
    ids: dict[str, uuid.UUID] = {}
    with engine.connect() as conn:
        programmes = dict(conn.execute(select(Programme.code, Programme.id)).all())
    docs: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    for doc in CORPUS:
        doc_id = ids[doc.slug] = uuid.uuid4()
        path = f"originals/{doc_id}.{doc.file_type}"
        docs.append(
            {
                "id": doc_id,
                "title": doc.title,
                "title_norm": normalize_for_search(doc.title),
                "original_filename": f"{doc.slug}.{doc.file_type}",
                "file_path": path,
                "viewer_path": path,
                "file_type": doc.file_type,
                "category": doc.category,
                "year": doc.year,
                "programme_id": programmes[doc.programme] if doc.programme else None,
                "uploaded_by": uploaded_by,
                "page_count": max(doc.pages),
                "status": doc.status,
                "language": doc.language,
                "sha256": hashlib.sha256(doc_id.bytes).hexdigest(),
                "size_bytes": 1000,
                "restricted": doc.restricted,
                "is_seed": doc.is_seed,
                "is_archived": doc.is_archived,
            }
        )
        for index, (number, text) in enumerate(sorted(doc.pages.items())):
            pages.append(
                {
                    "document_id": doc_id,
                    "page_number": number,
                    "text": text,
                    "text_norm": normalize_for_search(text),
                    "char_count": len(text),
                }
            )
            chunks.append(
                {
                    "document_id": doc_id,
                    "page_number": number,
                    "chunk_index": index,
                    "text": text,
                    "text_norm": normalize_for_search(text),
                    "char_start": 0,
                    "char_end": len(text),
                    "token_count": len(text) // 3,
                    "embedding": fake_embedding(text),
                    "embedding_model": "fake-embedding",
                }
            )
    with engine.begin() as conn:
        conn.execute(insert(Document), docs)
        conn.execute(insert(DocumentPage), pages)
        conn.execute(insert(Chunk), chunks)
    return ids
