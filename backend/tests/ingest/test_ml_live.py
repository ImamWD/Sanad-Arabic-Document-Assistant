"""The real ml service (int8 bge-m3 and bge-reranker-v2-m3), reached over the backend network.

Needs the running stack (`make up`). Marked `live`: skipped with a reason otherwise, or failed
with SANAD_REQUIRE_LIVE=1 (tests/conftest.py).
"""

import math
from collections.abc import Iterator

import pytest

from sanad.ingest.chunk import ChunkParams, chunk_document
from sanad.ingest.extract import extract_pages
from sanad.ingest.ml_client import MlClient
from sanad.text.arabic import clean_extracted
from tests.ingest.conftest import SEED, ml_url, needs_seed_files

pytestmark = pytest.mark.live(health=f"{ml_url()}/health", what="the ml service")

STAFF_AR = "بلغ عدد موظفي المؤسسة في نهاية عام 2021 نحو 71 موظفاً وموظفة، يساندهم 340 متطوعاً."
WATER_AR = "أعادت المؤسسة تأهيل 42 نقطة مياه ريفية في الهضبة الشرقية خلال عام 2019."
BOARD_AR = "ناقش مجلس الإدارة الميزانية المعدلة للعام المقبل ووافق عليها بالإجماع."


@pytest.fixture(scope="module")
def ml() -> Iterator[MlClient]:
    client = MlClient(ml_url(), timeout=300, embed_batch=8)
    yield client
    client.close()


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_health_names_the_models(ml: MlClient) -> None:
    assert ml.healthy()
    response = ml._client.get("/health").json()
    assert response["embed_model"] == "BAAI/bge-m3@onnx-int8"
    assert response["rerank_model"] == "BAAI/bge-reranker-v2-m3@onnx-int8"


def test_token_counts_have_no_special_tokens(ml: MlClient) -> None:
    empty, word, sentence = ml.count_tokens(["", "التعليم", STAFF_AR])
    assert empty == 0
    assert 1 <= word <= 4
    assert sentence > word


def test_embeddings_are_1024_d_unit_vectors(ml: MlClient) -> None:
    model, (vector,) = ml.embed([STAFF_AR])
    assert model == "BAAI/bge-m3@onnx-int8"
    assert len(vector) == 1024
    assert math.isclose(math.sqrt(sum(x * x for x in vector)), 1.0, rel_tol=1e-4)


def test_a_text_gets_the_same_vector_alone_or_in_company(ml: MlClient) -> None:
    _, (alone,) = ml.embed([WATER_AR])
    _, (_, in_company, _) = ml.embed([STAFF_AR, WATER_AR, BOARD_AR * 6])
    assert cosine(alone, in_company) > 0.99999


def test_questions_land_near_their_answers_across_languages(ml: MlClient) -> None:
    _, vectors = ml.embed(
        [
            "كم عدد العاملين في المؤسسة؟",
            "How many staff did the Foundation have?",
            STAFF_AR,
            WATER_AR,
            BOARD_AR,
        ]
    )
    question_ar, question_en, staff, water, board = vectors
    for question in (question_ar, question_en):
        assert cosine(question, staff) > cosine(question, water)
        assert cosine(question, staff) > cosine(question, board)


def test_rerank_scores_relevance_from_0_to_1_in_input_order(ml: MlClient) -> None:
    data = ml._post(
        "/rerank",
        {"query": "كم نقطة مياه أُعيد تأهيلها؟", "passages": [BOARD_AR, WATER_AR, STAFF_AR]},
    )
    board, water, staff = data["scores"]
    assert data["model"] == "BAAI/bge-reranker-v2-m3@onnx-int8"
    assert all(0.0 <= s <= 1.0 for s in (board, water, staff))
    assert water > 0.5 > max(board, staff)


@needs_seed_files
def test_real_chunks_respect_the_hard_maximum(ml: MlClient) -> None:
    pages = clean_extracted(
        [p.text for p in extract_pages(SEED / "documents" / "annual-report-2021.pdf")]
    )
    chunks = chunk_document(pages, ml.count_tokens, ChunkParams())
    assert len(chunks) >= len(pages)
    recounted = ml.count_tokens([c.text for c in chunks])
    assert max(recounted) <= 512
    assert recounted == [c.token_count for c in chunks]
    # Most pages of a report are well under 350 tokens: one or two chunks each.
    assert len(chunks) <= 2 * len(pages)
