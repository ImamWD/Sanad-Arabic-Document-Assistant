"""The three-band gate (DECISIONS D4), biased toward refusing."""

from enum import StrEnum


class Band(StrEnum):
    REFUSE = "refuse"  # top score < T_REFUSE: no LLM call
    LOW_CONFIDENCE = "low_confidence"  # T_REFUSE <= top score < T_CONFIDENT: amber banner
    ANSWER = "answer"  # top score >= T_CONFIDENT


def band_for(top_score: float | None, t_refuse: float, t_confident: float) -> Band:
    """Nothing retrieved (None) refuses, like a score below T_REFUSE."""
    if top_score is None or top_score < t_refuse:
        return Band.REFUSE
    if top_score < t_confident:
        return Band.LOW_CONFIDENCE
    return Band.ANSWER
