"""The ask pipeline with a fake LLM and fake retrieval: the gate, the stream order, the sentinel
holdback and post-validation (ROADMAP R1 acceptance, SYSTEM_DESIGN §6)."""

import asyncio
from dataclasses import replace
from typing import Any

import pytest

from sanad.llm.queue import GenerationQueue
from sanad.retrieval.ml import MlUnavailableError
from sanad.retrieval.pipeline import AskInput, nearest_documents, question_language, snippet
from tests.retrieval.fakes import (
    FakeHostedLlm,
    FakeLlm,
    FakeRetriever,
    FakeStore,
    make_candidate,
    make_user,
    names,
    pipeline,
    run,
)

pytestmark = pytest.mark.anyio

STRONG = [make_candidate(score=0.92), make_candidate("نص آخر عن البرنامج.", score=0.4)]
WEAK = [make_candidate(score=0.35)]
TOO_WEAK = [make_candidate(score=0.1, title="Annual Report 2023"), make_candidate(score=0.05)]
ANSWER = ["التحق 538 شاباً وشابة ", "بسوق العمل في 2021 [1]."]


async def test_answer_stream_order() -> None:
    llm = FakeLlm(ANSWER)
    p, store = pipeline(FakeRetriever(STRONG), llm)
    events = await run(p)

    assert names(events) == [
        "stage:searching",
        "stage:reading",
        "eta",
        "stage:writing",
        "token",
        "token",
        "final",
    ]
    reading = events[1].data
    assert reading == {"stage": "reading", "sources": 2, "band": "answer"}
    assert events[2].data == {"expected_seconds": 45, "capped": False}
    streamed = "".join(e.data["text"] for e in events if e.name == "token")
    assert streamed == "".join(ANSWER)

    final = events[-1].data
    assert final["outcome"] == "answered"
    assert final["band"] == "answer"
    assert final["refusal_reason"] is None
    assert final["answer"] == "التحق 538 شاباً وشابة بسوق العمل في 2021 [1]."
    assert [c["rank"] for c in final["citations"]] == [1]
    citation = final["citations"][0]
    assert citation["document_id"] == str(STRONG[0].document_id)
    assert citation["page_number"] == 6
    assert citation["file_type"] == "pdf"
    assert citation["is_converted"] is False
    assert final["nearest_documents"] == []

    (saved,) = store.saved
    assert saved.outcome == "answered"
    assert saved.answer == final["answer"]
    assert [(c.rank, c.chunk_id) for c in saved.citations] == [(1, STRONG[0].chunk_id)]
    assert saved.perf is not None and saved.perf.prompt_chars == llm.prompts[0].chars
    assert saved.llm_model == "fake-model"
    assert saved.session_id == "s1"


async def test_below_t_refuse_the_llm_is_never_called() -> None:
    llm = FakeLlm(ANSWER)
    p, store = pipeline(FakeRetriever(TOO_WEAK), llm)
    events = await run(p)

    assert llm.prompts == []
    assert names(events) == ["stage:searching", "stage:reading", "final"]
    assert events[1].data == {"stage": "reading", "sources": 0, "band": "refuse"}
    final = events[-1].data
    assert final["outcome"] == "no_answer"
    assert final["refusal_reason"] == "gate"
    assert final["band"] == "refuse"
    assert final["answer"] is None
    assert final["citations"] == []
    assert [d["title"] for d in final["nearest_documents"]] == [
        "Annual Report 2023",
        "التقرير السنوي 2021",
    ]
    (saved,) = store.saved
    assert (saved.outcome, saved.refusal_reason, saved.top_score) == ("no_answer", "gate", 0.1)
    assert saved.llm_provider is None


async def test_nothing_retrieved_is_a_gate_refusal() -> None:
    llm = FakeLlm(ANSWER)
    p, _ = pipeline(FakeRetriever([]), llm)
    events = await run(p)
    assert llm.prompts == []
    assert events[-1].data["refusal_reason"] == "gate"
    assert events[-1].data["nearest_documents"] == []


@pytest.mark.parametrize(
    "pieces",
    [["NO_ANSWER"], ["NO_", "ANSWER"], ["**NO_ANSWER**"], [" ", "`NO_ANSWER`", "\n"]],
)
async def test_sentinel_is_a_refusal_with_no_token_events(pieces: list[str]) -> None:
    p, store = pipeline(FakeRetriever(STRONG), FakeLlm(pieces))
    events = await run(p)

    assert "token" not in names(events)
    assert "stage:writing" not in names(events)
    final = events[-1].data
    assert (final["outcome"], final["refusal_reason"], final["answer"]) == (
        "no_answer",
        "sentinel",
        None,
    )
    assert final["band"] == "answer"
    assert final["citations"] == []
    assert len(final["nearest_documents"]) == 2
    assert store.saved[0].answer is None


async def test_a_late_sentinel_is_never_streamed_and_final_refuses() -> None:
    p, _ = pipeline(
        FakeRetriever(STRONG), FakeLlm(["The excerpts cover other years. ", "NO_ANSWER"])
    )
    events = await run(p)
    streamed = "".join(e.data["text"] for e in events if e.name == "token")
    assert streamed == "The excerpts cover other years. "
    assert events[-1].data["refusal_reason"] == "sentinel"


async def test_out_of_range_markers_are_dropped_from_the_final_answer() -> None:
    p, store = pipeline(
        FakeRetriever(STRONG), FakeLlm(["In 2021, 538 young people ", "found work [9][1][2]."])
    )
    final = (await run(p))[-1].data
    assert final["answer"] == "In 2021, 538 young people found work [1][2]."
    assert [c["document_id"] for c in final["citations"]] == [
        str(STRONG[0].document_id),
        str(STRONG[1].document_id),
    ]
    assert [c.rank for c in store.saved[0].citations] == [1, 2]


async def test_no_valid_marker_is_a_refusal_and_final_replaces_the_stream() -> None:
    p, store = pipeline(
        FakeRetriever(STRONG), FakeLlm(["In 2021, 538 young people found work [7]."])
    )
    events = await run(p)

    assert "token" in names(events)  # it streamed: `final` is what replaces it
    final = events[-1].data
    assert (final["outcome"], final["refusal_reason"], final["answer"]) == (
        "no_answer",
        "no_valid_citation",
        None,
    )
    assert store.saved[0].answer is None
    assert store.saved[0].citations == []


async def test_a_short_refused_answer_streams_nothing() -> None:
    p, _ = pipeline(FakeRetriever(STRONG), FakeLlm(["538."]))
    events = await run(p)
    assert names(events)[-2:] == ["eta", "final"]
    assert events[-1].data["refusal_reason"] == "no_valid_citation"


async def test_a_short_valid_answer_is_flushed_before_final() -> None:
    p, _ = pipeline(FakeRetriever(STRONG), FakeLlm(["84,000 [1]"]))
    events = await run(p)
    assert names(events)[-3:] == ["stage:writing", "token", "final"]
    assert events[-2].data == {"text": "84,000 [1]"}
    assert events[-1].data["answer"] == "84,000 [1]"


async def test_low_confidence_band_comes_before_the_first_token() -> None:
    p, store = pipeline(FakeRetriever(WEAK), FakeLlm(ANSWER))
    events = await run(p)
    reading = next(e for e in events if e.name == "stage" and e.data["stage"] == "reading")
    assert reading.data["band"] == "low_confidence"
    assert events.index(reading) < names(events).index("token")
    assert events[-1].data["outcome"] == "low_confidence"
    assert events[-1].data["band"] == "low_confidence"
    assert store.saved[0].outcome == "low_confidence"


async def test_only_top_k_excerpts_reach_the_prompt() -> None:
    candidates = [make_candidate(f"excerpt {i}", score=0.9 - i / 100) for i in range(8)]
    llm = FakeLlm(ANSWER)
    p, _ = pipeline(FakeRetriever(candidates), llm)
    await run(p)
    (prompt,) = llm.prompts
    assert prompt.excerpt_count == 3
    assert "excerpt 0" in prompt.user and "excerpt 2" in prompt.user
    assert "excerpt 3" not in prompt.user


async def test_provider_refusal_is_treated_as_the_sentinel() -> None:
    p, _ = pipeline(
        FakeRetriever(STRONG), FakeLlm(["partial text that was declined"], refused=True)
    )
    final = (await run(p))[-1].data
    assert (final["outcome"], final["refusal_reason"]) == ("no_answer", "sentinel")


async def test_search_unavailable_is_an_error_event() -> None:
    llm = FakeLlm(ANSWER)
    p, store = pipeline(FakeRetriever([], error=MlUnavailableError("down")), llm)
    events = await run(p)
    assert names(events) == ["stage:searching", "error"]
    assert events[-1].data == {"error": {"code": "SEARCH_UNAVAILABLE", "params": {}}}
    assert events[-1].status == 503
    assert llm.prompts == []
    assert store.saved[0].outcome == "error"
    assert store.saved[0].error_code == "SEARCH_UNAVAILABLE"


async def test_llm_unavailable_is_an_error_event() -> None:
    p, store = pipeline(FakeRetriever(STRONG), FakeLlm(fail=True))
    events = await run(p)
    assert names(events)[-1] == "error"
    assert events[-1].data["error"]["code"] == "LLM_UNAVAILABLE"
    assert store.saved[0].error_code == "LLM_UNAVAILABLE"


async def test_hosted_provider_never_receives_a_non_seed_excerpt() -> None:
    hosted = FakeHostedLlm(ANSWER)
    candidates = [
        make_candidate(score=0.9),
        make_candidate("نص من وثيقة حقيقية.", score=0.8, is_seed=False),
    ]
    p, store = pipeline(FakeRetriever(candidates), hosted)
    events = await run(p)
    assert hosted.sent == []
    assert events[-1].data["error"]["code"] == "HOSTED_LLM_NON_SEED_DATA"
    assert store.saved[0].error_code == "HOSTED_LLM_NON_SEED_DATA"


async def test_hosted_provider_with_seed_excerpts_answers() -> None:
    hosted = FakeHostedLlm(["The answer is 538 [1]."])
    p, _ = pipeline(FakeRetriever(STRONG), hosted)
    final = (await run(p))[-1].data
    assert final["outcome"] == "answered"
    assert len(hosted.sent) == 1


async def test_queued_comes_first_when_generation_is_busy() -> None:
    queue = GenerationQueue(1)
    gate = asyncio.Event()
    entered = asyncio.Event()

    async def occupy() -> None:
        async with queue.slot():
            entered.set()
            await gate.wait()

    holder = asyncio.create_task(occupy())
    await entered.wait()
    p, _ = pipeline(FakeRetriever(STRONG), FakeLlm(ANSWER), queue=queue)
    ask = AskInput(user=make_user(), session_id=None, question="How many found work?")
    stream = p.run(ask)
    first = await anext(stream)
    assert (first.name, first.data) == ("stage", {"stage": "queued", "position": 1})
    seen = [first]
    async for event in stream:
        seen.append(event)
        if event.name == "eta":
            assert event.data["expected_seconds"] == 90  # its own answer plus the one ahead
            gate.set()
    await holder
    assert names(seen)[:4] == ["stage:queued", "stage:searching", "stage:reading", "eta"]
    assert seen[-1].data["outcome"] == "answered"


async def test_queued_is_not_sent_when_a_slot_is_free() -> None:
    p, _ = pipeline(FakeRetriever(STRONG), FakeLlm(ANSWER))
    assert names(await run(p))[0] == "stage:searching"


async def test_eta_uses_measured_samples() -> None:
    from sanad.llm.eta import PerfSample

    measured = PerfSample(prompt_chars=1000, prompt_ms=2000, output_ms=4000, output_tokens=40)
    store = FakeStore(samples=[measured] * 5)
    llm = FakeLlm(ANSWER)
    p, _ = pipeline(FakeRetriever(STRONG), llm, store=store)
    events = await run(p)
    eta = next(e for e in events if e.name == "eta").data
    chars = llm.prompts[0].chars
    assert eta == {"expected_seconds": round((chars * 2 + 4000) / 1000, 1), "capped": False}


async def test_eta_waits_for_enough_samples() -> None:
    from sanad.llm.eta import PerfSample

    one = PerfSample(prompt_chars=1000, prompt_ms=2000, output_ms=4000, output_tokens=40)
    p, _ = pipeline(FakeRetriever(STRONG), FakeLlm(ANSWER), store=FakeStore(samples=[one]))
    eta = next(e for e in await run(p) if e.name == "eta").data
    assert eta == {"expected_seconds": 45, "capped": False}


def test_question_language_falls_back_to_the_ui_language() -> None:
    from sanad.core.models import Language

    user = make_user(lang=Language.AR)
    assert question_language("كم شاباً حصل على عمل؟", user) == "ar"
    assert question_language("How many found work?", user) == "en"
    assert question_language("2021?", user) == "ar"


def test_snippet_cuts_on_a_word() -> None:
    text = "word " * 100
    cut = snippet(text, 42)
    assert cut.endswith("…") and len(cut) <= 43 and "  " not in cut
    assert snippet("  short\n text ", 42) == "short text"


def test_nearest_documents_are_distinct() -> None:
    doc = make_candidate(score=0.5)
    same_doc = make_candidate(score=0.4, document_id=doc.document_id)
    other = make_candidate(score=0.3)
    assert nearest_documents([doc, same_doc, other], 3) == [doc, other]
    assert nearest_documents([doc, same_doc, other], 1) == [doc]


async def debug_run(p: object, question: str = "كم شاباً حصل على عمل في 2021؟") -> list[Any]:
    ask = AskInput(user=make_user(), session_id=None, question=question, debug=True)
    return [event async for event in p.run(ask)]  # type: ignore[attr-defined]


async def test_debug_adds_diagnostics_to_an_answer() -> None:
    candidates = [
        replace(c, file=f"doc-{i}.pdf", dense_rank=i + 1, lexical_rank=None)
        for i, c in enumerate(STRONG)
    ]
    retriever = FakeRetriever(candidates)
    retriever.timings_ms = {"embed": 5, "retrieve": 7, "rerank": 900}
    p, _ = pipeline(retriever, FakeLlm(ANSWER))
    final = (await debug_run(p))[-1].data
    diag = final["diagnostics"]
    assert [c["rank"] for c in diag["candidates"]] == [1, 2]
    first = diag["candidates"][0]
    assert first == {
        "rank": 1,
        "document_id": str(STRONG[0].document_id),
        "file": "doc-0.pdf",
        "page_number": 6,
        "chunk_id": str(STRONG[0].chunk_id),
        "rerank_score": 0.92,
        "dense_rank": 1,
        "lexical_rank": None,
    }
    assert (diag["top_score"], diag["band"], diag["llm_model"]) == (0.92, "answer", "fake-model")
    timings = diag["timings_ms"]
    assert (timings["embed"], timings["retrieve"], timings["rerank"]) == (5, 7, 900)
    assert (timings["first_token"], timings["generate"]) == (1200, 1500)
    assert timings["total"] >= 0
    assert STRONG[0].text not in str(diag)


async def test_debug_diagnostics_on_a_gate_refusal() -> None:
    llm = FakeLlm(ANSWER)
    p, _ = pipeline(FakeRetriever(TOO_WEAK), llm)
    diag = (await debug_run(p))[-1].data["diagnostics"]
    assert llm.prompts == []
    assert len(diag["candidates"]) == 2 and diag["band"] == "refuse"
    assert diag["timings_ms"]["first_token"] is None
    assert diag["timings_ms"]["generate"] is None


async def test_no_diagnostics_without_debug() -> None:
    p, _ = pipeline(FakeRetriever(STRONG), FakeLlm(ANSWER))
    assert "diagnostics" not in (await run(p))[-1].data
