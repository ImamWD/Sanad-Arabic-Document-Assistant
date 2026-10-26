"""Which programmes a question names (R1c): distinctive words, not the generic head."""

import json
from pathlib import Path

import pytest

from sanad.retrieval.programmes import ProgrammeName, named_programmes, rerank_query

MANIFEST = json.loads(
    (Path(__file__).resolve().parents[3] / "seed" / "manifest.json").read_text("utf-8")
)
PROGRAMMES = {p["code"]: ProgrammeName(p["name_ar"], p["name_en"]) for p in MANIFEST["programmes"]}


def codes(question: str) -> list[str]:
    named = named_programmes(question, list(PROGRAMMES.values()))
    return [code for code, p in PROGRAMMES.items() if p in named]


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        # The owner's two questions: «نظام» (system) where the documents say «برنامج».
        ("بدي اسال عن نظام الصحة المجتمعية، اشرحلي عنه اكثر", ["CHP"]),
        ("could you tell me about 'نظام الصحة المجتمعية'?", ["CHP"]),
        ("Tell me about the community health programme", ["CHP"]),
        ("حدثني عن برنامج الصحة المجتمعية", ["CHP"]),
        # A long name, partly mentioned, in dialect, with a clitic: «بالمناطق الريفية».
        ("احكيلي عن مشروع المياه بالمناطق الريفية شو صار فيه", ["WASH"]),
        ("What did the rural water project build?", ["WASH"]),
        ("What has the girls' education support work achieved?", ["GEP"]),
        ("ما نتائج مبادرة الحماية الاجتماعية؟", ["SPC"]),
        ("كم امرأة معيلة استفادت من سبل العيش؟", ["WLP"]),
    ],
)
def test_a_question_names_a_programme(question: str, expected: list[str]) -> None:
    assert codes(question) == expected


@pytest.mark.parametrize(
    "question",
    [
        "ما هي المناطق التي تعمل فيها المؤسسة؟",  # one word of a long name
        "كيف الصحة؟",  # one word of a two-word name
        "حدثني عن برنامج التمويل الأصغر في المؤسسة",  # a programme that doesn't exist
        "Tell me about the Foundation's microfinance programme",
        "كم شاباً حصل على عمل في برنامج الشباب؟",  # «الشباب» alone
        "How many weeks of paid maternity leave do the foundation's employees get?",
        "ما هو البرنامج؟",  # only the generic head
    ],
)
def test_no_programme_is_named(question: str) -> None:
    assert codes(question) == []


def test_the_word_order_matters_for_a_long_name() -> None:
    assert codes("الريفية المناطق") == []


def test_rerank_query_adds_the_official_names() -> None:
    chp = PROGRAMMES["CHP"]
    assert rerank_query("نظام الصحة المجتمعية؟", [chp]) == (
        f"نظام الصحة المجتمعية؟\n{chp.name_ar} | {chp.name_en}"
    )
    assert rerank_query("كيف الصحة؟", []) == "كيف الصحة؟"
