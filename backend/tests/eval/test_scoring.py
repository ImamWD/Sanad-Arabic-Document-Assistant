"""Scoring rules (SYSTEM_DESIGN §11) and the failure categories, as pure functions."""

import pytest

from sanad.eval.questions import ExpectedCitation, Question
from sanad.eval.scoring import (
    CandidatePage,
    Reply,
    best_expected_rank,
    has_fact,
    matching_text,
    missing_facts,
    score_item,
)
from tests.text.helpers import arabic_indic

AR21 = "annual-report-2021.pdf"
EVAL22 = "yep-final-evaluation-2022.pdf"
OTHER = "annual-report-2020.pdf"
ARABIC_1840 = arabic_indic("1") + "\N{ARABIC THOUSANDS SEPARATOR}" + arabic_indic("840")


def question(
    *facts: str,
    cites: tuple[tuple[str, int], ...] = ((AR21, 6), (EVAL22, 4)),
    kinds: tuple[str, ...] = ("factual", "numeric"),
    page_split: bool = False,
) -> Question:
    return Question(
        id="X01",
        language="ar",
        kinds=kinds,
        question="?",
        must_include=facts,
        expected_citations=tuple(ExpectedCitation(f, p) for f, p in cites),
        expected_outcome="answered",
        page_split=page_split,
    )


UNANSWERABLE = Question(
    id="X21",
    language="ar",
    kinds=("unanswerable", "near_miss"),
    question="?",
    must_include=(),
    expected_citations=(),
    expected_outcome="no_answer",
)


def candidates(*pages: tuple[str, int]) -> tuple[CandidatePage, ...]:
    return tuple(CandidatePage(rank, f, p, 0.9) for rank, (f, p) in enumerate(pages, start=1))


# --- fact matching ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fact", "answer"),
    [
        # Arabic-Indic digits in the answer, then in the fact
        ("538", f"التحق {arabic_indic('538')} شاباً وشابة بسوق العمل [1]"),
        (arabic_indic("58"), "Girls' enrolment was 58% in 2015 [1]."),
        ("1,840", "أحيلت 1840 حالة [1]"),  # separator in the fact only
        # Arabic-Indic digits with the Arabic thousands separator
        ("1,840", f"أحيلت {ARABIC_1840} حالة [1]"),
        ("140,000", "بلغت 140,000 دولار [1]"),
        ("82", "تلقى %82 من الأطفال اللقاحات [1]"),  # percent sign flipped by RTL
        ("82", "تلقى 82٪ من الأطفال [1]"),  # Arabic percent sign
        ("43.4", "أي 43.4% من المتدربين [1]"),
        ("36", "عمل البرنامج في 36 مدرسة [1]"),
        ("2021", "في عام" + "2021 [1]"),  # a number glued to an Arabic word
        ("285", "About USD 285 a month [1]."),
        ("بعد المدرسة", "بُعْدُ المَدْرَسَةِ عن السكن [1]"),  # diacritics in the answer
        ("بعد المدرسة", "بعد المدرســة [1]"),  # tatweel in the answer
        ("كريم العطار", "د. كَرِيم العَطَّار [1]"),
        ("ليلى الزين", "خلفاً لليلى الزين [1]"),  # a clitic in front of the name
        ("التعليم", "برنامج التعليــم [1]"),
        ("إدارة", "الادارة [1]"),  # hamza and alef forms fold together
    ],
)
def test_fact_found(fact: str, answer: str) -> None:
    assert has_fact(matching_text(answer), fact)


@pytest.mark.parametrize(
    ("fact", "answer"),
    [
        ("538", "1538 شاباً [1]"),  # a numeric fact is a whole number
        ("538", "538,000 دولار [1]"),
        ("538", "5.538 [1]"),
        ("43", "أي 43.4% [1]"),  # not the integer part of a decimal
        ("82", "82.5% [1]"),
        ("36", "منذ 2036 [1]"),
        ("2", "ten schools [2]"),  # a citation marker is not a fact
        ("1", "عشر مدارس [1، 2]"),
        ("3", "ten schools [ 3 ]"),
        ("1", f"عشر مدارس [{arabic_indic('1')}]"),
        ("41", "ارتفعت إلى 78% [1]"),
        ("كريم العطار", "د. كريم [1]"),
    ],
)
def test_fact_not_found(fact: str, answer: str) -> None:
    assert not has_fact(matching_text(answer), fact)


def test_missing_facts_keeps_the_order_of_the_yaml() -> None:
    assert missing_facts("ارتفعت من 41 [1]", ["41", "78", "75"]) == ("78", "75")
    assert missing_facts(None, ["41"]) == ("41",)


def test_best_expected_rank() -> None:
    expected = frozenset({(AR21, 6), (EVAL22, 4)})
    assert best_expected_rank(candidates((OTHER, 1), (EVAL22, 4), (AR21, 6)), expected) == 2
    assert best_expected_rank(candidates((OTHER, 1), (AR21, 7)), expected) is None


# --- answerable items ---------------------------------------------------------------------


def test_correct_with_arabic_digits_and_one_listed_citation() -> None:
    reply = Reply(
        outcome="answered", answer="٥٣٨ شاباً [1]", cited=((EVAL22, 4),), candidates=candidates()
    )
    score = score_item(question("538"), reply)
    assert score.correct
    assert score.category is None
    assert score.citation_ok


def test_low_confidence_counts_as_answered() -> None:
    reply = Reply(
        outcome="low_confidence", band="low_confidence", answer="538 [1]", cited=((AR21, 6),)
    )
    assert score_item(question("538"), reply).correct


def test_wrong_page_is_not_a_valid_citation() -> None:
    reply = Reply(
        outcome="answered",
        answer="538 [1]",
        cited=((AR21, 7),),
        candidates=candidates((AR21, 6), (AR21, 7)),
    )
    score = score_item(question("538"), reply)
    assert not score.correct
    assert not score.citation_ok
    assert score.category == "generation"
    assert score.expected_rank == 1


def test_unresolved_citation_never_matches() -> None:
    reply = Reply(outcome="answered", answer="538 [1]", cited=((None, 6),), candidates=candidates())
    assert not score_item(question("538"), reply).citation_ok


def test_missing_fact_with_the_page_retrieved_is_generation() -> None:
    reply = Reply(
        outcome="answered",
        answer="1240 متدرباً [1]",
        cited=((AR21, 6),),
        candidates=candidates((AR21, 6)),
    )
    score = score_item(question("538"), reply)
    assert score.category == "generation"
    assert score.missing_facts == ("538",)
    assert score.citation_ok
    assert score.retrieved is True


def test_no_expected_page_among_candidates_is_retrieval() -> None:
    reply = Reply(
        outcome="answered", answer="820 [1]", cited=((OTHER, 6),), candidates=candidates((OTHER, 6))
    )
    score = score_item(question("538"), reply)
    assert score.category == "retrieval"
    assert score.retrieved is False
    assert score.expected_rank is None


def test_without_diagnostics_the_cause_is_unclassified() -> None:
    reply = Reply(outcome="answered", answer="820 [1]", cited=((OTHER, 6),), candidates=None)
    score = score_item(question("538"), reply)
    assert score.category == "unclassified"
    assert score.retrieved is None


@pytest.mark.parametrize("reason", ["gate", "sentinel", "no_valid_citation"])
def test_refusing_an_answerable_item_is_a_false_refusal(reason: str) -> None:
    reply = Reply(outcome="no_answer", refusal_reason=reason, candidates=candidates((OTHER, 2)))
    score = score_item(question("538"), reply)
    assert not score.correct
    assert score.category == "false_refusal"
    assert score.missing_facts == ()  # a refusal is not judged on its facts


def test_page_split_failure_takes_the_page_split_category() -> None:
    split = question("1,840", cites=(("chp-evaluation-2024.pdf", 5),), page_split=True)
    refused = Reply(outcome="no_answer", refusal_reason="sentinel", candidates=candidates())
    assert score_item(split, refused).category == "page_split"
    wrong = Reply(outcome="answered", answer="72% [1]", cited=(("chp-evaluation-2024.pdf", 4),))
    assert score_item(split, wrong).category == "page_split"
    right = Reply(
        outcome="answered", answer="1,840 حالة [1]", cited=(("chp-evaluation-2024.pdf", 5),)
    )
    assert score_item(split, right).correct


# --- cross-document items -----------------------------------------------------------------

CROSS = question(
    "41",
    "78",
    cites=(
        ("wash-baseline-survey-2017.pdf", 3),
        ("wash-final-evaluation-2021.pdf", 2),
        (AR21, 8),
    ),
    kinds=("cross_document", "temporal", "numeric"),
)


def test_cross_document_needs_every_fact_but_any_one_listed_citation() -> None:
    reply = Reply(
        outcome="answered",
        answer="ارتفعت من 41% [1] إلى ٧٨٪ [2]",
        cited=(("wash-baseline-survey-2017.pdf", 3), (OTHER, 1)),
    )
    assert score_item(CROSS, reply).correct


def test_cross_document_with_one_fact_missing_fails() -> None:
    reply = Reply(
        outcome="answered",
        answer="بلغت 41% في 2017 [1]",
        cited=(("wash-baseline-survey-2017.pdf", 3),),
        candidates=candidates(("wash-baseline-survey-2017.pdf", 3)),
    )
    score = score_item(CROSS, reply)
    assert not score.correct
    assert score.missing_facts == ("78",)
    assert score.category == "generation"


# --- unanswerable items -------------------------------------------------------------------


def test_refusing_an_unanswerable_item_is_correct() -> None:
    reply = Reply(outcome="no_answer", refusal_reason="gate", candidates=candidates((OTHER, 4)))
    score = score_item(UNANSWERABLE, reply)
    assert score.correct
    assert score.category is None
    assert score.retrieved is None  # recall is about answerable items only


@pytest.mark.parametrize("outcome", ["answered", "low_confidence"])
def test_answering_an_unanswerable_item_is_an_invented_answer(outcome: str) -> None:
    reply = Reply(outcome=outcome, answer="68 [1]", cited=((OTHER, 4),), candidates=candidates())
    score = score_item(UNANSWERABLE, reply)
    assert not score.correct
    assert score.category == "invented_answer"


# --- errors -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        Reply(outcome=None, error_code="LLM_UNAVAILABLE"),
        Reply(outcome="error", error_code="OUTCOME_ERROR"),
    ],
)
def test_a_failed_request_is_an_error_for_any_item(reply: Reply) -> None:
    for item in (question("538"), question("1,840", page_split=True), UNANSWERABLE):
        score = score_item(item, reply)
        assert not score.correct
        assert score.category == "error"
