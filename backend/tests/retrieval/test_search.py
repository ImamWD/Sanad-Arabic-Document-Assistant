"""Hybrid retrieval in Postgres: access control at every stage, the lexical OR query, filters.

A Viewer and the guest must never retrieve a restricted document (client Q2), the guest only
seed documents (Q4), and nobody archived or unfinished documents.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from sanad.core.config import get_settings
from sanad.core.db import create_engine
from sanad.core.models import User
from sanad.documents.models import Chunk
from sanad.retrieval.search import (
    SqlRetriever,
    dense_ids,
    lexical_ids,
    lexical_query,
    load_candidates,
    rerank_passage,
)
from sanad.retrieval.settings import RetrievalSettings
from sanad.retrieval.types import Filters
from sanad.text.arabic import strip_marks
from tests.retrieval.corpus import CORPUS, WLP_QUESTION, FakeMl, fake_embedding

pytestmark = pytest.mark.anyio

NEVER = {"budget-2024-draft", "indexing-report"}
YEARS = {doc.slug: doc.year or 0 for doc in CORPUS}


@pytest.fixture
async def aengine(settings: object) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(get_settings())
    try:
        yield engine
    finally:
        await engine.dispose()


async def chunk_docs(aengine: AsyncEngine, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    async with AsyncSession(aengine) as db:
        return set((await db.scalars(select(Chunk.document_id).where(Chunk.id.in_(ids)))).all())


async def stages(
    aengine: AsyncEngine, user: User, question: str, filters: Filters | None = None
) -> dict[str, set[uuid.UUID]]:
    """The documents behind each retrieval stage, for one question."""
    filters = filters or Filters()
    async with AsyncSession(aengine) as db:
        dense = await dense_ids(db, user, filters, fake_embedding(question), 100)
        lexical = await lexical_ids(db, user, filters, question, 100)
        loaded = await load_candidates(db, user, filters, dense + lexical)
    return {
        "dense": await chunk_docs(aengine, dense),
        "lexical": await chunk_docs(aengine, lexical),
        "loaded": {c.document_id for c in loaded},
    }


async def test_viewer_never_retrieves_the_restricted_document(
    aengine: AsyncEngine, users: dict[str, User], corpus: dict[str, uuid.UUID]
) -> None:
    for who in ("viewer", "guest"):
        found = await stages(aengine, users[who], WLP_QUESTION)
        for stage, docs in found.items():
            assert corpus["wlp-donor-agreement-2022"] not in docs, (who, stage)
            assert docs, (who, stage)  # it did search: other agreements matched


async def test_editor_and_admin_retrieve_the_restricted_document(
    aengine: AsyncEngine, users: dict[str, User], corpus: dict[str, uuid.UUID]
) -> None:
    for who in ("editor", "admin"):
        found = await stages(aengine, users[who], WLP_QUESTION)
        for stage, docs in found.items():
            assert corpus["wlp-donor-agreement-2022"] in docs, (who, stage)


async def test_guest_retrieves_seed_documents_only(
    aengine: AsyncEngine, users: dict[str, User], corpus: dict[str, uuid.UUID]
) -> None:
    question = "مذكرة داخلية عن رواتب فريق المشروع"
    guest = await stages(aengine, users["guest"], question)
    viewer = await stages(aengine, users["viewer"], question)
    assert corpus["staff-memo"] in viewer["lexical"]
    for docs in guest.values():
        assert corpus["staff-memo"] not in docs


async def test_nobody_retrieves_archived_or_unfinished_documents(
    aengine: AsyncEngine, users: dict[str, User], corpus: dict[str, uuid.UUID]
) -> None:
    never = {corpus[slug] for slug in NEVER}
    for user in users.values():
        for docs in (await stages(aengine, user, "رواتب فريق المشروع في المسودة")).values():
            assert not docs & never


async def test_lexical_matches_through_diacritics_and_tatweel(
    aengine: AsyncEngine, users: dict[str, User], corpus: dict[str, uuid.UUID]
) -> None:
    found = await stages(aengine, users["viewer"], "ما رَواتِب فريــق المشروع؟")
    assert corpus["spc-donor-agreement-2023"] in found["lexical"]


async def test_lexical_is_an_or_of_content_terms(
    aengine: AsyncEngine, users: dict[str, User], corpus: dict[str, uuid.UUID]
) -> None:
    # Most of these words appear in no chunk: an AND query would match nothing.
    found = await stages(aengine, users["viewer"], "كم كان المتطوعون والمتبرعون volunteers هناك؟")
    assert found["lexical"] == {corpus["annual-report-2023-en"]}


def test_lexical_query_skips_stopword_only_questions() -> None:
    assert lexical_query("ما هو؟") is None
    assert lexical_query("رواتب الفريق") is not None


async def test_filters_narrow_the_scope(
    aengine: AsyncEngine, users: dict[str, User], corpus: dict[str, uuid.UUID]
) -> None:
    editor = users["editor"]
    by_year = await stages(aengine, editor, "رواتب فريق المشروع", Filters(year_from=2023))
    assert {corpus["spc-donor-agreement-2023"], corpus["staff-memo"]} <= by_year["lexical"]
    for docs in by_year.values():
        assert all(YEARS[slug] >= 2023 for slug, doc_id in corpus.items() if doc_id in docs)
    by_category = await stages(
        aengine, editor, "رواتب فريق المشروع", Filters(category="donor_agreement", year_to=2018)
    )
    for docs in by_category.values():
        assert docs == {corpus["wash-donor-agreement-2018"]}


async def test_retriever_reranks_with_the_title(
    aengine: AsyncEngine, users: dict[str, User], corpus: dict[str, uuid.UUID]
) -> None:
    ml = FakeMl()
    retriever = SqlRetriever(aengine, ml, RetrievalSettings())
    result = await retriever.retrieve(users["editor"], WLP_QUESTION, Filters())

    assert ml.embedded == [strip_marks(WLP_QUESTION)]
    (passages,) = ml.reranked
    assert all("\n" in p for p in passages)
    top = result.candidates[0]
    assert top.document_id == corpus["wlp-donor-agreement-2022"]
    assert result.top_score == top.score
    # The title tells the WLP budget row apart from the identical rows of other agreements.
    order = [(c.document_id, c.page_number) for c in result.candidates]
    wlp_budget = order.index((corpus["wlp-donor-agreement-2022"], 3))
    assert wlp_budget < order.index((corpus["spc-donor-agreement-2023"], 3))
    assert wlp_budget < order.index((corpus["wash-donor-agreement-2018"], 5))
    assert [c.score for c in result.candidates] == sorted(
        (c.score for c in result.candidates), reverse=True
    )
    assert rerank_passage(top) == f"{top.title}\n{top.text}"


async def test_retriever_without_anything_to_search_never_calls_ml(
    aengine: AsyncEngine, users: dict[str, User], corpus: dict[str, uuid.UUID]
) -> None:
    ml = FakeMl()
    retriever = SqlRetriever(aengine, ml, RetrievalSettings())
    result = await retriever.retrieve(users["viewer"], WLP_QUESTION, Filters(year_from=2099))
    assert result.candidates == []
    assert ml.embedded == [] and ml.reranked == []


async def test_candidates_carry_what_the_citation_card_needs(
    aengine: AsyncEngine, users: dict[str, User], corpus: dict[str, uuid.UUID]
) -> None:
    retriever = SqlRetriever(aengine, FakeMl(), RetrievalSettings())
    result = await retriever.retrieve(users["guest"], "رواتب فريق المشروع موازنة", Filters())
    spc = next(c for c in result.candidates if c.document_id == corpus["spc-donor-agreement-2023"])
    assert (spc.file_type, spc.is_converted, spc.is_seed, spc.language) == (
        "docx",
        True,
        True,
        "ar",
    )
    assert spc.char_end == len(spc.text)


async def test_candidates_carry_programme_and_year(
    aengine: AsyncEngine, users: dict[str, User], corpus: dict[str, uuid.UUID]
) -> None:
    retriever = SqlRetriever(aengine, FakeMl(), RetrievalSettings())
    result = await retriever.retrieve(users["editor"], WLP_QUESTION, Filters())
    wlp = next(c for c in result.candidates if c.document_id == corpus["wlp-donor-agreement-2022"])
    assert wlp.year == 2022
    assert wlp.programme == "برنامج سُبل العيش للنساء المعيلات"
    english = await retriever.retrieve(users["editor"], "How many volunteers?", Filters())
    report = next(c for c in english.candidates if c.file == "annual-report-2023-en.pdf")
    assert (report.programme, report.year) == (None, 2023)


async def test_embed_and_rerank_get_the_question_without_marks(
    aengine: AsyncEngine, users: dict[str, User], corpus: dict[str, uuid.UUID]
) -> None:
    ml = FakeMl()
    retriever = SqlRetriever(aengine, ml, RetrievalSettings())
    await retriever.retrieve(users["editor"], "كَمْ رَوَاتِبُ فَرِيقِ المَشْرُوعِ؟", Filters())
    assert ml.embedded == ["كم رواتب فريق المشروع؟"]
    assert ml.rerank_queries == ["كم رواتب فريق المشروع؟"]


async def test_the_reranker_hears_the_official_name_of_a_named_programme(
    aengine: AsyncEngine, users: dict[str, User], corpus: dict[str, uuid.UUID]
) -> None:
    ml = FakeMl()
    retriever = SqlRetriever(aengine, ml, RetrievalSettings())
    await retriever.retrieve(users["editor"], "احكيلي عن مشروع المياه بالمناطق الريفية", Filters())
    await retriever.retrieve(users["editor"], "ما هي المناطق التي تعمل فيها المؤسسة؟", Filters())
    named, plain = ml.rerank_queries
    assert named.startswith("احكيلي عن مشروع المياه بالمناطق الريفية\n")
    assert "مشروع المياه والإصحاح البيئي في المناطق الريفية" in named
    assert "Rural Water, Sanitation and Hygiene Project" in named
    assert plain == "ما هي المناطق التي تعمل فيها المؤسسة؟"
    # The embedding gets the question alone.
    assert ml.embedded[0] == "احكيلي عن مشروع المياه بالمناطق الريفية"
