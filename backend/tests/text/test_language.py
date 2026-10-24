import pytest

from sanad.text.arabic import TATWEEL, detect_language
from tests.text.helpers import BARNAMAJ, TAMKEEN


@pytest.mark.parametrize(
    "question",
    [
        # From eval/questions.yaml: a code, tatweel and full tashkeel don't change the answer.
        "ما قيمة المنحة التي قدمتها مؤسسة فارنهولت لمشروع YEP-2021-03؟",
        "في كم مدرسة عمل برنامج التعليــم الخاص بالفتيات خلال 2021؟",
        "كَمْ مُتَطَوِّعًا وَمُتَطَوِّعَةً سَانَدُوا المُؤَسَّسَةَ فِي عَامِ 2021؟",
        "كم تتسلم الأسرة المستفيدة كل شهر في مشروع الدعم النقدي SPC-2023-01؟",
    ],
)
def test_arabic_questions(question: str) -> None:
    assert detect_language(question) == "ar"


@pytest.mark.parametrize(
    "question",
    [
        (
            "What girls' enrolment rate had the GEP-2019-02 target schools reached when the "
            "project ended in 2022?"
        ),
        "How many weeks of paid maternity leave do the foundation's employees get?",
    ],
)
def test_english_questions(question: str) -> None:
    assert detect_language(question) == "en"


def test_mixed_question() -> None:
    assert detect_language("What does مؤسسة الريحان للتنمية publish each year?") == "mixed"


def test_url_letters_do_not_count() -> None:
    text = "التقرير الكامل على https://example.org/annual-report-2021-full-version"
    assert detect_language(text) == "ar"


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("التقارير UN", "ar"),  # 8 Arabic letters of 10: exactly 80%
        ("UNICEF Report عام", "en"),  # 3 of 15: exactly 20%
    ],
)
def test_thresholds_are_inclusive(text: str, language: str) -> None:
    assert detect_language(text) == language


@pytest.mark.parametrize("text", ["", "2021", "1,250 — 52%", TATWEEL * 3])
def test_no_letters_is_mixed(text: str) -> None:
    assert detect_language(text) == "mixed"


def test_presentation_forms_count_as_arabic() -> None:
    assert detect_language(f"{BARNAMAJ} {TAMKEEN}") == "ar"
