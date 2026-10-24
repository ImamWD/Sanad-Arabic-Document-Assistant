import pytest

from sanad.text.arabic import sentence_spans, split_sentences
from tests.text.helpers import arabic_indic


def test_arabic_marks_always_end_a_clause() -> None:
    text = "هل نجح البرنامج؟ نعم، فقد ارتفعت نسبة التوظيف؛ وتوسع العمل إلى قريتين."
    assert split_sentences(text) == [
        "هل نجح البرنامج؟",
        "نعم،",
        "فقد ارتفعت نسبة التوظيف؛",
        "وتوسع العمل إلى قريتين.",
    ]


def test_arabic_marks_split_even_without_a_space() -> None:
    assert split_sentences("التعليم،الصحة،المياه") == ["التعليم،", "الصحة،", "المياه"]


def test_decimals_codes_and_urls_are_not_split() -> None:
    text = (
        "بلغ متوسط الأجر 12.5 دينار يومياً في مشروع YEP-2021-03. "
        "التفاصيل في https://example.org/r?id=7 والملحق ب.3 من التقرير."
    )
    assert split_sentences(text) == [
        "بلغ متوسط الأجر 12.5 دينار يومياً في مشروع YEP-2021-03.",
        "التفاصيل في https://example.org/r?id=7 والملحق ب.3 من التقرير.",
    ]


def test_arabic_decimal_separator_is_not_a_boundary() -> None:
    text = arabic_indic("ارتفع المعدل إلى 12\N{ARABIC DECIMAL SEPARATOR}5 نقطة.")
    assert split_sentences(text) == [text]


def test_english_sentences() -> None:
    text = (
        "Did the project meet its target? Yes! Enrolment rose to 61.4% by 2022. See example.org/r."
    )
    assert split_sentences(text) == [
        "Did the project meet its target?",
        "Yes!",
        "Enrolment rose to 61.4% by 2022.",
        "See example.org/r.",
    ]


def test_initials_and_abbreviations_do_not_end_a_sentence() -> None:
    text = "أعدّ التقرير د. سامي خوري و م. ليلى الزين. Reviewed by J. Hartmann."
    assert split_sentences(text) == [
        "أعدّ التقرير د. سامي خوري و م. ليلى الزين.",
        "Reviewed by J. Hartmann.",
    ]


def test_a_number_before_a_full_stop_still_ends_the_sentence() -> None:
    assert split_sentences("بلغ عدد المدارس 5. وفي العام التالي 7.") == [
        "بلغ عدد المدارس 5.",
        "وفي العام التالي 7.",
    ]


def test_closing_quotes_stay_with_their_sentence() -> None:
    text = "قالت المديرة: «انتهى المشروع.» ثم شكرت الفريق. هل انتهى حقاً؟! نعم."
    assert split_sentences(text) == [
        "قالت المديرة: «انتهى المشروع.»",
        "ثم شكرت الفريق.",
        "هل انتهى حقاً؟!",
        "نعم.",
    ]


def test_blank_line_ends_a_sentence_but_a_wrapped_line_does_not() -> None:
    wrapped = "\n".join(["يغطي هذا التقرير عام 2024", "وهو عام انتقالي في مسيرة البرنامج"])
    text = "\n".join(["## مقدمة", "", "  ", wrapped])
    assert split_sentences(text) == ["## مقدمة", wrapped]


def test_spans_point_into_the_original_text() -> None:
    text = "  نعم.   تم ذلك في 2021؟  "
    spans = sentence_spans(text)
    assert spans == [(2, 6), (9, 24)]
    assert [text[s:e] for s, e in spans] == ["نعم.", "تم ذلك في 2021؟"]


@pytest.mark.parametrize("text", ["", "   \n\n  ", "؟"])
def test_nothing_to_split(text: str) -> None:
    expected = [text.strip()] if text.strip() else []
    assert split_sentences(text) == expected
