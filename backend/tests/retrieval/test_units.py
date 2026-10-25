"""Small pure pieces: the gate, RRF, the ETA, the generation queue and the settings."""

import asyncio

import pytest
from pydantic import ValidationError

from sanad.llm.eta import MIN_SECONDS, PerfSample, expected_seconds
from sanad.llm.queue import GenerationQueue
from sanad.retrieval.fuse import rrf
from sanad.retrieval.gate import Band, band_for
from sanad.retrieval.settings import RetrievalSettings


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (None, Band.REFUSE),
        (0.0, Band.REFUSE),
        (0.199, Band.REFUSE),
        (0.2, Band.LOW_CONFIDENCE),
        (0.599, Band.LOW_CONFIDENCE),
        (0.6, Band.ANSWER),
        (1.0, Band.ANSWER),
    ],
)
def test_three_bands(score: float | None, band: Band) -> None:
    assert band_for(score, 0.2, 0.6) is band


def test_thresholds_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        RetrievalSettings(t_refuse=0.7, t_confident=0.5)


def test_rrf_rewards_agreement_and_keeps_ties_in_order() -> None:
    dense = ["a", "b", "c"]
    lexical = ["c", "d", "a"]
    assert rrf([dense, lexical], k=60, limit=10) == ["a", "c", "b", "d"]
    assert rrf([dense, lexical], k=60, limit=2) == ["a", "c"]
    assert rrf([["x", "y"], []], k=60, limit=5) == ["x", "y"]


def test_eta_defaults_before_any_sample() -> None:
    assert expected_seconds([], prompt_chars=9000, ahead=0, default_seconds=60) == 60
    assert expected_seconds([], prompt_chars=9000, ahead=2, default_seconds=60) == 180


def test_eta_scales_with_the_prompt_and_the_queue() -> None:
    samples = [
        PerfSample(prompt_chars=10_000, prompt_ms=30_000, output_ms=5_000),
        PerfSample(prompt_chars=8_000, prompt_ms=24_000, output_ms=4_000),
        PerfSample(prompt_chars=12_000, prompt_ms=36_000, output_ms=6_000),
        # A prompt restored from cache: absurdly fast. The median ignores it.
        PerfSample(prompt_chars=10_000, prompt_ms=200, output_ms=5_000),
        PerfSample(prompt_chars=0, prompt_ms=0, output_ms=0),
    ]
    # 3 ms per character, median output 5 s.
    assert expected_seconds(samples, prompt_chars=9_000, ahead=0, default_seconds=60) == 32.0
    # Plus one median total (31.5 s) per generation ahead.
    assert expected_seconds(samples, prompt_chars=9_000, ahead=1, default_seconds=60) == 63.5


def test_eta_is_never_zero() -> None:
    samples = [PerfSample(prompt_chars=100, prompt_ms=0, output_ms=0)]
    assert expected_seconds(samples, prompt_chars=100, ahead=0, default_seconds=60) == MIN_SECONDS


@pytest.mark.anyio
async def test_queue_reports_who_waits() -> None:
    queue = GenerationQueue(1)
    assert queue.ahead() == 0
    first_in = asyncio.Event()
    release = asyncio.Event()

    async def hold() -> None:
        async with queue.slot():
            first_in.set()
            await release.wait()

    first = asyncio.create_task(hold())
    await first_in.wait()
    assert queue.ahead() == 1
    second = asyncio.create_task(hold())
    await asyncio.sleep(0)
    assert queue.ahead() == 2

    second.cancel()  # a client that leaves while waiting leaves the queue
    with pytest.raises(asyncio.CancelledError):
        await second
    assert queue.ahead() == 1
    release.set()
    await first
    assert queue.ahead() == 0
