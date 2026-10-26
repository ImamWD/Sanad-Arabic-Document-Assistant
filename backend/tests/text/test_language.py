import pytest

from sanad.text.arabic import TATWEEL, detect_language, dominant_language
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


@pytest.mark.parametrize("text", ["", "2021", "1,250 (52%)", TATWEEL * 3])
def test_no_letters_is_mixed(text: str) -> None:
    assert detect_language(text) == "mixed"


def test_presentation_forms_count_as_arabic() -> None:
    assert detect_language(f"{BARNAMAJ} {TAMKEEN}") == "ar"


# --- dominant_language: the language a question is asked in ---------------------------------

LEFT_QUOTE = "\N{LEFT DOUBLE QUOTATION MARK}"
RIGHT_QUOTE = "\N{RIGHT DOUBLE QUOTATION MARK}"


@pytest.mark.parametrize(
    "question",
    [
        # D32: the quoted Arabic name has about as many letters as the English around it.
        "could you tell me about 'نظام الصحة المجتمعية'?",
        "What does «نظام الصحة المجتمعية» cover?",
        f"What is {LEFT_QUOTE}برنامج تمكين الشباب{RIGHT_QUOTE} about?",
        'What does "بلغ عدد الأسر المستفيدة ألفي أسرة في عام 2022" refer to?',
        # Apostrophes are not quotes: read as one quoted span, "'s the budget of the girls'"
        # would leave 4 English letters to 11 Arabic.
        "What's the budget of the girls' برنامج تمكين؟",
        (
            "What girls' enrolment rate had the GEP-2019-02 target schools reached when the "
            "project ended in 2022?"
        ),
        "What can you tell me about the Foundation's microfinance programme?",
    ],
)
def test_english_questions_that_quote_arabic(question: str) -> None:
    assert dominant_language(question) == "en"


@pytest.mark.parametrize(
    "question",
    [
        "ما قيمة المنحة التي قدمتها مؤسسة فارنهولت لمشروع WASH-2018-01؟",
        # Codes don't count: "WASH" alone has as many letters as the Arabic.
        "ما هو WASH-2018-01؟",
        "كم بلغت مساهمة UNICEF في مشروع المياه؟",
        'كم بلغت مساهمة "UNICEF" في مشروع المياه؟',
        'ما معنى "Community Health Programme" في التقرير؟',
        # Levantine (D31, D33) and Gulf dialect.
        "بدي اسال عن نظام الصحة المجتمعية، اشرحلي عنه اكثر",
        "احكيلي عن مشروع المياه بالمناطق الريفية، شو اللي انعمل فيه؟",
        "وش سوت المؤسسة في برنامج تعليم البنات؟",
        "ما هو التقرير على https://example.org/annual-report-2021-full-version",
    ],
)
def test_arabic_questions_with_english_names_and_codes(question: str) -> None:
    assert dominant_language(question) == "ar"


@pytest.mark.parametrize(
    "question",
    [
        # Unquoted names: 23 English letters to 19 Arabic, and 15 Arabic to 23 English.
        "What does مؤسسة الريحان للتنمية publish each year?",
        "كم بلغت ميزانية Girls Education Programme في 2021؟",
    ],
)
def test_too_close_to_call(question: str) -> None:
    assert dominant_language(question) is None


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("عامل ab", "ar"),  # 4 Arabic letters to 2: exactly twice
        ("عام ab", None),  # 3 to 2
        ("data في", "en"),  # 4 to 2
        ("dat في", None),  # 3 to 2
    ],
)
def test_the_ratio_is_inclusive(text: str, language: str | None) -> None:
    assert dominant_language(text) == language


@pytest.mark.parametrize("text", ["", "2021", "1,250 (52%)", TATWEEL * 3, "YEP-2021-03"])
def test_no_letters_is_none(text: str) -> None:
    assert dominant_language(text) is None


def test_a_question_wholly_in_quotes_still_counts() -> None:
    assert dominant_language('"What is the GEP budget?"') == "en"
    assert dominant_language("«ما هو برنامج الصحة المجتمعية؟»") == "ar"
