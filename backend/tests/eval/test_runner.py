"""Reply resolution, the preflight and the HTTP client, against the fake API."""

from typing import Any

import httpx2
import pytest

from sanad.core.config import get_settings
from sanad.eval.client import EVAL_BAD_RESPONSE, EVAL_TRANSPORT_ERROR, AskReply, SanadClient
from sanad.eval.questions import ExpectedCitation, Question
from sanad.eval.runner import build_row, document_files, preflight, resolve, timings_of
from tests.eval.fakes import FakeSanad, answer, refuse, seed_document

AR21 = "annual-report-2021.pdf"
AR20 = "annual-report-2020.pdf"

QUESTION = Question(
    id="X01",
    language="ar",
    kinds=("factual",),
    question="كم عدد الشباب؟",
    must_include=("538",),
    expected_citations=(ExpectedCitation(AR21, 6),),
    expected_outcome="answered",
)


def fake_password() -> str:
    return get_settings().demo_editor_password.get_secret_value()


def files_of(*docs: dict[str, object]) -> dict[str, str]:
    return document_files(docs)


# --- resolve ------------------------------------------------------------------------------


def test_resolve_maps_document_ids_to_files() -> None:
    ar21, ar20 = seed_document(AR21), seed_document(AR20)
    data: dict[str, Any] = {
        "outcome": "answered",
        "band": "answer",
        "refusal_reason": None,
        "answer": "538 [1]",
        "citations": [{"rank": 1, "document_id": ar21["id"], "page_number": 6}],
        "diagnostics": {
            "candidates": [
                {"rank": 2, "document_id": ar21["id"], "page_number": 6, "score": 0.7},
                {"rank": 1, "document_id": ar20["id"], "page_number": 3, "score": 0.8},
            ]
        },
    }
    reply = resolve(AskReply(200, data, 10), files_of(ar21, ar20))
    assert reply.cited == ((AR21, 6),)
    assert reply.candidates is not None
    assert [(c.rank, c.file, c.page, c.score) for c in reply.candidates] == [
        (1, AR20, 3, 0.8),
        (2, AR21, 6, 0.7),
    ]


def test_resolve_accepts_the_tolerated_aliases() -> None:
    data: dict[str, Any] = {
        "outcome": "no_answer",
        "answer": None,
        "citations": [],
        "timings_ms": {"total": 900, "rerank": 400.5, "note": "x"},
        "diagnostics": {"candidates": [{"file": AR21, "page": 6, "rerank_score": 0.4}]},
    }
    reply = resolve(AskReply(200, data, 10), {})
    assert reply.candidates is not None
    assert reply.candidates[0].file == AR21
    assert reply.candidates[0].page == 6
    assert reply.candidates[0].score == 0.4
    assert reply.candidates[0].rank == 1
    assert timings_of(data) == {"total": 900.0, "rerank": 400.5}


def test_resolve_without_diagnostics_has_no_candidates() -> None:
    data = {"outcome": "answered", "answer": "538 [1]", "citations": []}
    assert resolve(AskReply(200, data, 10), {}).candidates is None


@pytest.mark.parametrize("outcome", [None, "maybe", 3])
def test_resolve_rejects_an_unknown_outcome(outcome: object) -> None:
    reply = resolve(AskReply(200, {"outcome": outcome}, 10), {})
    assert reply.outcome is None
    assert reply.error_code == EVAL_BAD_RESPONSE


def test_resolve_keeps_the_error_code_of_a_failed_request() -> None:
    reply = resolve(AskReply(503, None, 10, "LLM_UNAVAILABLE"), {})
    assert reply.outcome is None
    assert reply.error_code == "LLM_UNAVAILABLE"


def test_build_row_records_the_refusal_reason_band_and_rank() -> None:
    ar21, ar20 = seed_document(AR21), seed_document(AR20)
    data: dict[str, Any] = {
        "outcome": "no_answer",
        "band": "refuse",
        "refusal_reason": "gate",
        "answer": None,
        "citations": [],
        "diagnostics": {
            "candidates": [
                {"rank": 1, "document_id": ar20["id"], "page_number": 2, "score": 0.12},
                {"rank": 2, "document_id": ar21["id"], "page_number": 6, "score": 0.10},
            ],
            "timings_ms": {"total": 1500, "retrieval": 300},
            "llm_model": "fake-model",
        },
    }
    row = build_row(QUESTION, AskReply(200, data, 1600), files_of(ar21, ar20))
    assert row.category == "false_refusal"
    assert (row.refusal_reason, row.band) == ("gate", "refuse")
    assert row.expected_rank == 2
    assert row.top_score == 0.12
    assert row.server_ms == 1500
    assert row.wall_ms == 1600
    assert row.expected == [f"{AR21} p6"]
    assert row.llm_model == "fake-model"


# --- preflight ----------------------------------------------------------------------------


def test_preflight_passes_on_a_ready_seed_corpus() -> None:
    assert preflight([seed_document(AR21), seed_document(AR20)], [QUESTION]) == []


def test_preflight_refuses_non_seed_documents_in_scope() -> None:
    docs = [seed_document(AR21), seed_document("upload.pdf", is_seed=False)]
    (problem,) = preflight(docs, [QUESTION])
    assert "1 non-seed document" in problem
    assert "upload.pdf" not in problem  # never names a client file


def test_preflight_ignores_archived_non_seed_documents() -> None:
    docs = [seed_document(AR21), seed_document("old.pdf", is_seed=False, is_archived=True)]
    assert preflight(docs, [QUESTION]) == []


@pytest.mark.parametrize(
    ("docs", "expected"),
    [
        ([seed_document(AR20)], "no seed document"),
        ([seed_document(AR21, status="processing")], "not 'ready'"),
        ([seed_document(AR21, is_archived=True)], "archived"),
        ([seed_document(AR21, is_seed=False, is_archived=True)], "no seed document"),
    ],
)
def test_preflight_needs_every_expected_file_ready(
    docs: list[dict[str, object]], expected: str
) -> None:
    (problem,) = preflight(docs, [QUESTION])
    assert problem.startswith(AR21)
    assert expected in problem


# --- client -------------------------------------------------------------------------------


def test_client_pages_through_every_document() -> None:
    docs = [seed_document(f"doc-{n:03}.pdf") for n in range(230)]
    fake = FakeSanad({}, docs)
    with SanadClient("http://api:8000", timeout=5, transport=fake.transport) as client:
        client.login_guest()
        assert len(client.documents()) == 230
    assert fake.calls["/api/documents"] == 3


def test_client_sends_csrf_cookie_and_debug() -> None:
    ar21 = seed_document(AR21)
    fake = FakeSanad({QUESTION.question: answer("538 [1]", (AR21, 6))}, [ar21])
    with SanadClient("http://api:8000/", timeout=5, transport=fake.transport) as client:
        client.login("editor@sanad.example", fake_password())
        reply = client.ask(QUESTION.question, debug=True)
    assert reply.status == 200
    assert reply.data is not None
    assert "diagnostics" in reply.data
    assert fake.asked == [{"question": QUESTION.question, "debug": True}]


def test_client_reports_server_errors_by_code() -> None:
    fake = FakeSanad({}, [])
    with SanadClient("http://api:8000", timeout=5, transport=fake.transport) as client:
        reply = client.ask("?", debug=False)  # not signed in
    assert reply.status == 401
    assert reply.error_code == "UNAUTHENTICATED"


def test_client_turns_a_dropped_connection_into_an_error_reply() -> None:
    def drop(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadError("connection reset", request=request)

    with SanadClient("http://api:8000", timeout=5, transport=httpx2.MockTransport(drop)) as client:
        reply = client.ask("?", debug=False)
    assert reply.status is None
    assert reply.error_code == EVAL_TRANSPORT_ERROR


def test_refusals_carry_no_answer_text() -> None:
    ar21 = seed_document(AR21)
    fake = FakeSanad({QUESTION.question: refuse("sentinel", [(AR21, 6)])}, [ar21])
    with SanadClient("http://api:8000", timeout=5, transport=fake.transport) as client:
        client.login("editor@sanad.example", fake_password())
        reply = client.ask(QUESTION.question, debug=True)
    assert reply.data is not None
    assert reply.data["answer"] is None
