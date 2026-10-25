"""The "this answer may take about S seconds" estimate (SYSTEM_DESIGN §6, client addition to D3).

Built from this machine's measured answers (`llm_perf_samples`) for the configured model:
- prompt processing scales with the prompt, so it uses the median milliseconds per prompt
  character, times this prompt's size;
- generation uses the median output time (answers are short and similar in length);
- each generation ahead in the queue adds the median total.

Medians, so a prompt restored from the model's cache (S3 saw implausibly fast prompt speeds)
or a cold model load doesn't swing the estimate. Before any sample exists the estimate is
ETA_DEFAULT_SECONDS per generation.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

MIN_SECONDS = 1.0


@dataclass(frozen=True)
class PerfSample:
    prompt_chars: int
    prompt_ms: int
    output_ms: int


def expected_seconds(
    samples: Sequence[PerfSample], prompt_chars: int, ahead: int, default_seconds: float
) -> float:
    usable = [s for s in samples if s.prompt_chars > 0]
    if not usable:
        return round(default_seconds * (1 + ahead), 1)
    ms_per_char = median(s.prompt_ms / s.prompt_chars for s in usable)
    output_ms = median(s.output_ms for s in usable)
    total_ms = median(s.prompt_ms + s.output_ms for s in usable)
    own_ms = prompt_chars * ms_per_char + output_ms
    # The UI ignores a non-positive estimate, so never send one.
    return max(round((own_ms + ahead * total_ms) / 1000, 1), MIN_SECONDS)
