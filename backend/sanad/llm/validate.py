"""Post-validation of a generated answer (SYSTEM_DESIGN §6, DECISIONS D4).

No valid citation means no answer:
- `NO_ANSWER` anywhere in the output is a refusal (`sentinel`). Biased toward refusing, so a
  sentinel wrapped in markdown or followed by an explanation still counts.
- Markers outside 1..K are dropped. An answer with no surviving marker is a refusal
  (`no_valid_citation`), and so is one with markers but no words.
- The surviving markers are renumbered 1..m in order of first appearance, so the answer reads
  [1], [2], ... and citation `rank` equals the marker shown.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

SENTINEL = "NO_ANSWER"
_SENTINEL_RE = re.compile(re.escape(SENTINEL), re.IGNORECASE)

# `[3]`, `[1, 4]` or `[1، 4]`. `\d` matches any Unicode decimal digit and `int()` reads them,
# so Arabic-Indic markers (`[٢]`) need no special handling.
_MARKER_RE = re.compile(r"\[[^\S\n]*(\d{1,3}(?:[^\S\n]*[,،][^\S\n]*\d{1,3})*)[^\S\n]*\]")
_MARKER_NUMBER_RE = re.compile(r"\d+")
# Left behind when a marker is dropped: a space before punctuation, or doubled spaces.
_SPACE_BEFORE_PUNCT_RE = re.compile(r"[^\S\n]+([.,;:!?،؛؟])")
_SPACE_RUN_RE = re.compile(r"[^\S\n]{2,}")


class RefusalReason(StrEnum):
    GATE = "gate"  # retrieval below T_REFUSE: the documents don't cover this
    SENTINEL = "sentinel"  # the model said NO_ANSWER
    NO_VALID_CITATION = "no_valid_citation"  # the model answered without a usable [n]


@dataclass(frozen=True)
class Validated:
    """`answer` is set (with renumbered markers) exactly when `refusal` is None. `cited` lists
    the excerpt numbers (1-based, as sent to the model) behind markers [1], [2], ..."""

    answer: str | None
    refusal: RefusalReason | None
    cited: tuple[int, ...] = ()


def contains_sentinel(text: str) -> bool:
    return _SENTINEL_RE.search(text) is not None


def marker_numbers(text: str) -> list[int]:
    """Every number inside a citation marker, in order, valid or not."""
    return [
        int(n) for m in _MARKER_RE.finditer(text) for n in _MARKER_NUMBER_RE.findall(m.group(1))
    ]


def validate(raw: str, excerpt_count: int) -> Validated:
    if contains_sentinel(raw):
        return Validated(None, RefusalReason.SENTINEL)

    order: dict[int, int] = {}  # excerpt number -> new marker number

    def rewrite(match: re.Match[str]) -> str:
        kept = []
        for number in (int(n) for n in _MARKER_NUMBER_RE.findall(match.group(1))):
            if not 1 <= number <= excerpt_count:
                continue
            new = order.setdefault(number, len(order) + 1)
            if new not in kept:
                kept.append(new)
        return "".join(f"[{n}]" for n in kept)

    answer = _MARKER_RE.sub(rewrite, raw)
    answer = _SPACE_RUN_RE.sub(" ", _SPACE_BEFORE_PUNCT_RE.sub(r"\1", answer)).strip()
    words = _MARKER_RE.sub("", answer)
    if not order or not any(ch.isalnum() for ch in words):
        return Validated(None, RefusalReason.NO_VALID_CITATION)
    return Validated(answer, None, tuple(order))
