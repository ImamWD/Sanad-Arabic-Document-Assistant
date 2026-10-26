"""Small pure pieces: the gate, RRF, the ETA, the generation queue and the settings."""

import asyncio

import pytest
from pydantic import ValidationError

from sanad.llm.eta import MIN_SECONDS, Estimate, PerfSample, expected_seconds
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


def eta(samples: list[PerfSample], prompt_chars: int = 9_000, ahead: int = 0) -> Estimate:
    return expected_seconds(
        samples, prompt_chars, ahead, default_seconds=60, min_samples=5, max_seconds=600
    )


def sample(
    prompt_ms: int, output_ms: int, tokens: int | None = 40, chars: int = 9_000
) -> PerfSample:
    return PerfSample(
        prompt_chars=chars, prompt_ms=prompt_ms, output_ms=output_ms, output_tokens=tokens
    )


def test_eta_defaults_before_any_sample() -> None:
    assert eta([]) == Estimate(60, capped=False)
    assert eta([], ahead=2) == Estimate(180, capped=False)


def test_the_owners_two_samples_give_the_default_not_1474_seconds() -> None:
    """R1d regression: two samples, one timed while three models shared the CPU."""
    owners = [
        PerfSample(prompt_chars=9_000, prompt_ms=43_500, output_ms=2_200, output_tokens=23),
        PerfSample(prompt_chars=9_000, prompt_ms=112_000, output_ms=584_000, output_tokens=143),
    ]
    assert eta(owners) == Estimate(60, capped=False)
    assert eta(owners, ahead=1) == Estimate(120, capped=False)


def test_measured_samples_count_only_from_the_minimum() -> None:
    four = [sample(27_000, 4_000)] * 4
    assert eta(four) == Estimate(60, capped=False)
    # 3 ms per prompt character and 100 ms per token over a 40-token answer.
    assert eta([*four, sample(27_000, 4_000)]) == Estimate(31.0, capped=False)


def test_generation_is_a_rate_so_a_long_answer_is_not_a_slow_one() -> None:
    # The same 100 ms per token; answers of 20 to 160 tokens (median 40).
    samples = [
        sample(27_000, 2_000, 20),
        sample(27_000, 4_000, 40),
        sample(27_000, 4_000, 40),
        sample(27_000, 8_000, 80),
        sample(27_000, 16_000, 160),
    ]
    assert eta(samples) == Estimate(27.0 + 4.0, capped=False)


def test_outliers_are_dropped_before_the_medians() -> None:
    typical = [sample(27_000, 4_000)] * 5
    slow_generation = sample(27_000, 400_000)  # 100 times slower per token
    cached_prompt = sample(200, 4_000)  # a prompt restored from cache
    with_outliers = [*typical, slow_generation, slow_generation, cached_prompt, cached_prompt]
    assert eta(with_outliers) == eta(typical) == Estimate(31.0, capped=False)


def test_each_generation_ahead_adds_one_typical_generation() -> None:
    samples = [sample(27_000, 4_000)] * 5
    # Its own 31 s, plus 27 s + 4 s for the one ahead.
    assert eta(samples, ahead=1) == Estimate(62.0, capped=False)


def test_the_estimate_is_capped() -> None:
    slow = [sample(900_000, 40_000)] * 5  # 100 ms per character: 900 s of prompt
    assert eta(slow) == Estimate(600, capped=True)
    assert eta([], ahead=20) == Estimate(600, capped=True)


def test_samples_without_token_counts_use_the_output_time() -> None:
    samples = [sample(27_000, 4_000, tokens=None)] * 5
    assert eta(samples) == Estimate(31.0, capped=False)


def test_eta_is_never_zero() -> None:
    zero = [PerfSample(prompt_chars=100, prompt_ms=1, output_ms=0, output_tokens=10)] * 5
    assert eta(zero, prompt_chars=100) == Estimate(MIN_SECONDS, capped=False)


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
