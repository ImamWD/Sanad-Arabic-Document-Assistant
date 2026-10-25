from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from sanad_ml.main import MAX_CHARS, MAX_TEXTS, create_app
from tests.fakes import FakeEngine


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(FakeEngine)) as test_client:
        yield test_client


def test_embed_returns_one_normalised_vector_per_text(client: TestClient) -> None:
    response = client.post("/embed", json={"texts": ["التعليم", "a longer text"]})
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "fake/embed@test"
    assert body["dim"] == 4
    assert len(body["embeddings"]) == 2
    for vector in body["embeddings"]:
        assert len(vector) == 4
        assert abs(sum(x * x for x in vector) - 1.0) < 1e-5


def test_embed_empty_list(client: TestClient) -> None:
    response = client.post("/embed", json={"texts": []})
    assert response.status_code == 200
    assert response.json()["embeddings"] == []


def test_rerank_scores_keep_input_order(client: TestClient) -> None:
    response = client.post(
        "/rerank",
        json={"query": "water points", "passages": ["no match", "water points built", "water"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "fake/rerank@test"
    assert body["scores"] == [0.0, 1.0, 0.5]


def test_tokenize_counts(client: TestClient) -> None:
    response = client.post("/tokenize", json={"texts": ["one two", "", "a b c"]})
    assert response.status_code == 200
    assert response.json() == {"model": "fake/embed@test", "counts": [2, 0, 3]}


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/embed", {"texts": ["x"] * (MAX_TEXTS + 1)}),
        ("/embed", {"texts": ["x" * (MAX_CHARS + 1)]}),
        ("/tokenize", {"texts": "not a list"}),
        ("/rerank", {"query": "q", "passages": ["x"] * (MAX_TEXTS + 1)}),
        ("/rerank", {"passages": ["x"]}),
    ],
)
def test_oversized_or_malformed_requests_are_rejected(
    client: TestClient, path: str, body: dict[str, object]
) -> None:
    assert client.post(path, json=body).status_code == 422
