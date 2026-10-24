"""Post-validation: no valid citation means no answer (DECISIONS D4, SYSTEM_DESIGN §6)."""

import pytest

from sanad.llm.validate import RefusalReason, Validated, contains_sentinel, marker_numbers, validate
from tests.text.helpers import arabic_indic


def test_valid_answer_keeps_markers() -> None:
    result = validate("In 2021, 538 young people found work [1].", excerpt_count=3)
    assert result == Validated("In 2021, 538 young people found work [1].", None, (1,))


def test_out_of_range_markers_are_dropped() -> None:
    result = validate("التحق 538 شاباً بسوق العمل [2][7]. وبلغت النسبة 43.4% [0].", 3)
    assert result.answer == "التحق 538 شاباً بسوق العمل [1]. وبلغت النسبة 43.4%."
    assert result.cited == (2,)


def test_markers_are_renumbered_by_first_appearance() -> None:
    result = validate("A [3]. B [1][3]. C [2].", 3)
    assert result.answer == "A [1]. B [2][1]. C [3]."
    assert result.cited == (3, 1, 2)


def test_grouped_and_arabic_indic_markers() -> None:
    result = validate(f"بلغ العدد 538 [{arabic_indic('1، 3')}] وكان ذلك في 2021 [2, 9].", 3)
    assert result.answer == "بلغ العدد 538 [1][2] وكان ذلك في 2021 [3]."
    assert result.cited == (1, 3, 2)


def test_no_valid_marker_is_a_refusal() -> None:
    assert validate("538 young people found work.", 3) == Validated(
        None, RefusalReason.NO_VALID_CITATION
    )


def test_only_out_of_range_markers_is_a_refusal() -> None:
    result = validate("538 young people found work [4][12].", 3)
    assert result.refusal is RefusalReason.NO_VALID_CITATION
    assert result.answer is None


def test_markers_without_words_is_a_refusal() -> None:
    assert validate(" [1] [2] ", 3).refusal is RefusalReason.NO_VALID_CITATION


def test_empty_output_is_a_refusal() -> None:
    assert validate("", 3).refusal is RefusalReason.NO_VALID_CITATION


@pytest.mark.parametrize(
    "raw",
    [
        "NO_ANSWER",
        "  NO_ANSWER\n",
        "**NO_ANSWER**",
        "`no_answer`",
        "The excerpts do not say. NO_ANSWER",
        "NO_ANSWER [1]",
        "538 [1]. NO_ANSWER",
    ],
)
def test_sentinel_anywhere_is_a_refusal(raw: str) -> None:
    assert validate(raw, 3) == Validated(None, RefusalReason.SENTINEL)


def test_contains_sentinel() -> None:
    assert contains_sentinel("x no_answer y")
    assert not contains_sentinel("NO ANSWER")


def test_marker_numbers() -> None:
    assert marker_numbers(f"a [1] b [2, 7] c [{arabic_indic('3')}] d [x] e [1000]") == [1, 2, 7, 3]
