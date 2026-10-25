"""Sentinel holdback: the NO_ANSWER sentinel is never streamed (SYSTEM_DESIGN §6)."""

from collections.abc import Sequence

import pytest

from sanad.llm.holdback import SentinelHoldback


def feed_all(pieces: Sequence[str]) -> tuple[str, str, bool]:
    """(released while streaming, held at the end, sentinel seen)."""
    hb = SentinelHoldback()
    released = "".join(hb.feed(p) for p in pieces)
    return released, hb.finish(), hb.sentinel_seen


@pytest.mark.parametrize(
    "pieces",
    [
        ["NO_ANSWER"],
        ["NO", "_ANS", "WER"],
        ["  ", "**NO_", "ANSWER**", "\n"],
        ["no_answer"],
    ],
)
def test_sentinel_alone_releases_nothing(pieces: list[str]) -> None:
    released, held, seen = feed_all(pieces)
    assert (released, held, seen) == ("", "", True)


def test_nothing_is_released_before_sixteen_non_space_characters() -> None:
    hb = SentinelHoldback()
    assert hb.feed("التحق 538 شاباً ") == ""  # 13 non-space characters
    released = hb.feed("بسوق العمل [1].")
    assert released == "التحق 538 شاباً بسوق العمل [1]."


def test_short_answer_is_held_until_the_end() -> None:
    released, held, seen = feed_all(["84,000 ", "[1]"])
    assert (released, held, seen) == ("", "84,000 [1]", False)


def test_a_possible_sentinel_prefix_is_held_back() -> None:
    hb = SentinelHoldback()
    assert hb.feed("The figure in the agreement is NO_ANS") == "The figure in the agreement is "
    assert hb.feed("WER") == ""
    assert hb.sentinel_seen
    assert hb.finish() == ""


def test_a_held_prefix_that_turns_out_harmless_is_released() -> None:
    hb = SentinelHoldback()
    assert hb.feed("Salaries for the project team: N") == "Salaries for the project team: "
    assert hb.feed("o change [1].") == "No change [1]."


def test_sentinel_after_streaming_started_stops_releasing() -> None:
    released, held, seen = feed_all(
        ["The excerpts mention salaries for other programmes", " but ", "NO_ANSWER", " here."]
    )
    assert released == "The excerpts mention salaries for other programmes but "
    assert (held, seen) == ("", True)


def test_ordinary_answer_streams_through() -> None:
    pieces = ["In 2021, ", "538 young people ", "found work [1]."]
    released, held, seen = feed_all(pieces)
    assert released + held == "".join(pieces)
    assert not seen
