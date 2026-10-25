"""`strip_marks`: tashkeel and tatweel go, everything else stays as written."""

from sanad.text.arabic import TATWEEL, normalize_for_search, strip_marks


def test_fully_diacritised_question_loses_only_its_marks() -> None:
    # D15 in eval/dev_questions.yaml is written with full tashkeel.
    assert strip_marks("فِي أَيِّ سَنَةٍ بَدَأَتِ المُؤَسَّسَةُ عَمَلَهَا؟") == ("في أي سنة بدأت المؤسسة عملها؟")


def test_tatweel_and_superscript_alef_go() -> None:
    assert strip_marks(f"التعلي{TATWEEL * 3}م") == "التعليم"
    assert strip_marks("هٰذا") == "هذا"


def test_letters_hamza_and_teh_marbuta_are_kept() -> None:
    # Unlike normalize_for_search: no alef, yeh or teh marbuta folding.
    for word in ("أهداف", "إدارة", "مسؤولية", "مستشفى", "مدرسة"):
        assert strip_marks(word) == word
        assert normalize_for_search(word) != word


def test_latin_digits_codes_and_spacing_are_untouched() -> None:
    text = "Project YEP-2021-03  costs 450,000 USD.\nNext line"
    assert strip_marks(text) == text
