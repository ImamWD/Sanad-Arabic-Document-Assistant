"""The "this answer may take about S seconds" estimate (SYSTEM_DESIGN §6, client addition to D3).

Built from this machine's measured answers (`llm_perf_samples`) for the configured model:
- **Enough samples first.** Fewer than ETA_MIN_SAMPLES measured answers give
  ETA_DEFAULT_SECONDS per generation: a median of two samples is their mean, and one slow
  answer then decides the estimate (R1d: the owner saw "about 1,474 seconds").
- **Rates, not raw times.** Prompt processing is milliseconds per prompt character, times this
  prompt's size. Generation is milliseconds per output token, times the median answer
  length, so a long answer doesn't count as a slow one.
- **Outliers out.** A sample whose prompt rate or generation rate is more than three times
  slower or faster than the median rate is dropped before the medians are taken: an answer
  timed while other models shared the CPU, or a prompt restored from the model's cache (S3
  saw implausibly fast prompt speeds).
- **Each generation ahead** in the queue adds one typical generation (median prompt time plus
  the typical generation time).
- **A cap.** Above ETA_MAX_SECONDS the estimate is the cap, marked `capped`: past that point
  the honest message is "the server is busy", not a precise number.

Samples are only recorded for answers that finished: a cancelled request stores nothing, and
the time spent waiting in the generation queue is outside the measured window.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

MIN_SECONDS = 1.0
# A rate more than this many times off the median (either way) is an outlier.
OUTLIER_FACTOR = 3.0


@dataclass(frozen=True)
class PerfSample:
    prompt_chars: int
    prompt_ms: int
    output_ms: int
    output_tokens: int | None = None


@dataclass(frozen=True)
class Estimate:
    seconds: float
    capped: bool  # the real estimate was above the cap: show "the server is busy"


def _within(rate: float, typical: float) -> bool:
    return typical / OUTLIER_FACTOR <= rate <= typical * OUTLIER_FACTOR


def _keep_typical(samples: Sequence[PerfSample]) -> list[PerfSample]:
    """The samples whose prompt and generation rates are within OUTLIER_FACTOR of the median."""
    prompt_rate = median(s.prompt_ms / s.prompt_chars for s in samples)
    rated = [s for s in samples if s.output_tokens]
    output_rate = (
        median(s.output_ms / s.output_tokens for s in rated if s.output_tokens) if rated else None
    )
    kept = []
    for s in samples:
        if not _within(s.prompt_ms / s.prompt_chars, prompt_rate):
            continue
        if (
            output_rate
            and s.output_tokens
            and not _within(s.output_ms / s.output_tokens, output_rate)
        ):
            continue
        kept.append(s)
    return kept


def _generation_ms(samples: Sequence[PerfSample]) -> float:
    """Median ms per output token times the median answer length; median output time when the
    provider reported no token counts."""
    rated = [s for s in samples if s.output_tokens]
    if not rated:
        return float(median(s.output_ms for s in samples))
    per_token = median(s.output_ms / s.output_tokens for s in rated if s.output_tokens)
    tokens = median(s.output_tokens for s in rated if s.output_tokens)
    return per_token * tokens


def _finish(seconds: float, max_seconds: float) -> Estimate:
    if seconds > max_seconds:
        return Estimate(max_seconds, capped=True)
    # The UI ignores a non-positive estimate, so never send one.
    return Estimate(max(round(seconds, 1), MIN_SECONDS), capped=False)


def expected_seconds(
    samples: Sequence[PerfSample],
    prompt_chars: int,
    ahead: int,
    default_seconds: float,
    *,
    min_samples: int,
    max_seconds: float,
) -> Estimate:
    usable = [s for s in samples if s.prompt_chars > 0 and s.prompt_ms > 0]
    if len(usable) < min_samples:
        return _finish(default_seconds * (1 + ahead), max_seconds)
    typical = _keep_typical(usable) or usable
    ms_per_char = median(s.prompt_ms / s.prompt_chars for s in typical)
    generation = _generation_ms(typical)
    one_generation = median(s.prompt_ms for s in typical) + generation
    own = prompt_chars * ms_per_char + generation
    return _finish((own + ahead * one_generation) / 1000, max_seconds)
