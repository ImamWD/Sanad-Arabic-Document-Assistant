import pytest

from sanad.text.arabic import ALEF, TEH_MARBUTA, normalize_for_search
from tests.text.helpers import ISTIJABA, arabic_indic, persian_digits, seed_lines, shaped


def test_tatweel_is_ignored() -> None:
    assert normalize_for_search("التعليــم") == normalize_for_search("التعليم")


def test_diacritics_are_ignored() -> None:
    assert normalize_for_search("التَّعْلِيم") == normalize_for_search("التعليم")


def test_fully_diacritised_question_matches_plain_one() -> None:
    # T10 in eval/questions.yaml is written with full tashkeel.
    voweled = "كَمْ مُتَطَوِّعًا وَمُتَطَوِّعَةً سَانَدُوا المُؤَسَّسَةَ فِي عَامِ 2021؟"
    plain = "كم متطوعا ومتطوعة ساندوا المؤسسة في عام 2021؟"
    assert normalize_for_search(voweled) == normalize_for_search(plain)


def test_superscript_alef_is_stripped() -> None:
    assert normalize_for_search("هٰذا التقرير") == "هذا التقرير"


@pytest.mark.parametrize(
    ("written", "normalised"),
    [
        ("أهداف المشروع", "اهداف المشروع"),
        ("إدارة البرنامج", "اداره البرنامج"),
        ("آذار/مارس 2025", "اذار/مارس 2025"),
        ("ٱلتعليم الأساسي", "التعليم الاساسي"),
        ("مستشفى المدينة", "مستشفي المدينه"),
        ("رئيس الهيئة", "رييس الهييه"),
        ("مسؤول المؤسسة", "مسوول الموسسه"),
    ],
)
def test_alef_hamza_and_yeh_forms_unify(written: str, normalised: str) -> None:
    assert normalize_for_search(written) == normalised


def test_alef_variants_match_each_other() -> None:
    variants = ["الأطفال", "الإطفال", "الآطفال", "الاطفال"]
    assert len({normalize_for_search(v) for v in variants}) == 1


def test_decomposed_hamza_is_composed_before_unifying() -> None:
    decomposed = ALEF + "\N{ARABIC HAMZA ABOVE}" + "طفال المدارس"
    assert (
        normalize_for_search(decomposed) == normalize_for_search("أطفال المدارس") == "اطفال المدارس"
    )


def test_taa_marbuta_folds_by_default() -> None:
    assert normalize_for_search("المدرسة الثانوية") == normalize_for_search("المدرسه الثانويه")


def test_taa_marbuta_can_be_kept() -> None:
    kept = normalize_for_search("المدرسة الثانوية", fold_taa_marbuta=False)
    assert kept == "المدرسة الثانوية"
    assert kept.endswith(TEH_MARBUTA)
    assert kept != normalize_for_search("المدرسه الثانويه", fold_taa_marbuta=False)


def test_persian_yeh_and_keheh_map_to_arabic() -> None:
    persian_typed = "التعل\N{ARABIC LETTER FARSI YEH}م و\N{ARABIC LETTER KEHEH}تب"
    assert normalize_for_search(persian_typed) == normalize_for_search("التعليم وكتب")


def test_arabic_indic_and_persian_digits_become_latin() -> None:
    expected = "تخرجت دفعة 2022 في 15/03/2023"
    assert normalize_for_search(
        arabic_indic("تخرجت دفعة 2022 في 15/03/2023")
    ) == normalize_for_search(expected)
    assert normalize_for_search(
        persian_digits("تخرجت دفعة 2022 في 15/03/2023")
    ) == normalize_for_search(expected)


def test_number_tokens_written_three_ways_match() -> None:
    forms = [arabic_indic("1\N{ARABIC THOUSANDS SEPARATOR}250"), "1,250", "1250"]
    assert {normalize_for_search(f) for f in forms} == {"1250"}


def test_numbers_match_inside_sentences() -> None:
    arabic = arabic_indic(
        "أتمّ 1\N{ARABIC THOUSANDS SEPARATOR}600 متدرب التدريب بنسبة 52\N{ARABIC PERCENT SIGN}"
    )
    assert normalize_for_search(arabic) == normalize_for_search("أتم 1,600 متدرب التدريب بنسبة %52")


def test_presentation_forms_fold() -> None:
    taleem = shaped(
        "ALEF ISOLATED",
        "LAM INITIAL",
        "TEH MEDIAL",
        "AIN MEDIAL",
        "LAM MEDIAL",
        "YEH MEDIAL",
        "MEEM FINAL",
    )
    assert normalize_for_search(taleem) == normalize_for_search("التعليم")


def test_lam_alef_ligature_folds_to_two_letters() -> None:
    assert normalize_for_search(ISTIJABA) == normalize_for_search("الاستجابة")


def test_presentation_form_harakat_do_not_split_the_word() -> None:
    word = "ع" + "\N{ARABIC FATHA ISOLATED FORM}" + "ام" + "\N{ARABIC FATHATAN ISOLATED FORM}"
    assert normalize_for_search(word) == "عام"
    medial = "التعل" + "\N{ARABIC KASRA MEDIAL FORM}" + "يم"
    assert normalize_for_search(medial) == "التعليم"


def test_code_stays_one_token_inside_arabic() -> None:
    text = "ما قيمة المنحة التي قدمتها مؤسسة فارنهولت لمشروع YEP-2021-03 خلال المرحلة الأولى؟"
    assert "yep-2021-03" in normalize_for_search(text).split()


def test_url_stays_intact_inside_arabic() -> None:
    url = "https://example.org/reports?year=2021&ids=1,250&q=%20"
    text = f"التقرير الكامل منشور على {url} ويمكن تنزيله مجاناً"
    assert url in normalize_for_search(text).split()


def test_latin_is_lower_cased_urls_included() -> None:
    text = "راجع تقرير UNICEF على https://Example.org/Reports/2021"
    assert normalize_for_search(text) == "راجع تقرير unicef علي https://example.org/reports/2021"


def test_arabic_letters_and_digits_are_separated() -> None:
    assert normalize_for_search("بين 2021 و2023") == "بين 2021 و 2023"
    assert normalize_for_search("صدر في 2021م") == "صدر في 2021 م"


def test_bidi_and_zero_width_characters_are_removed() -> None:
    text = (
        "\N{RIGHT-TO-LEFT MARK}برنامج\N{ZERO WIDTH NON-JOINER} التعليم"
        "\N{LEFT-TO-RIGHT EMBEDDING} YEP-2021-03\N{POP DIRECTIONAL FORMATTING}"
        " بنسبة 52\N{RIGHT-TO-LEFT MARK}%\N{ZERO WIDTH NO-BREAK SPACE}"
        " edu\N{SOFT HYPHEN}cation"
    )
    assert normalize_for_search(text) == "برنامج التعليم yep-2021-03 بنسبه 52% education"


def test_whitespace_collapses_newlines_included() -> None:
    text = "  التقرير \n\t السنوي\N{NO-BREAK SPACE}\N{THIN SPACE}لعام   2021 \n"
    assert normalize_for_search(text) == "التقرير السنوي لعام 2021"


@pytest.mark.parametrize("fold", [True, False])
def test_idempotent_on_the_seed_corpus(fold: bool) -> None:
    for line in seed_lines():
        once = normalize_for_search(line, fold_taa_marbuta=fold)
        assert normalize_for_search(once, fold_taa_marbuta=fold) == once, line
