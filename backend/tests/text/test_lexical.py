import pytest

from sanad.text.arabic import (
    ARABIC_STOPWORDS,
    ENGLISH_STOPWORDS,
    TEH_MARBUTA,
    lexical_terms,
    normalize_for_search,
    search_tokens,
    strip_clitics,
)
from tests.text.helpers import seed_lines


def test_arabic_question_keeps_content_terms_and_the_code() -> None:
    question = "ما قيمة المنحة التي قدمتها مؤسسة فارنهولت لمشروع YEP-2021-03؟"
    assert lexical_terms(question) == [
        "قيمه",
        "المنحه",
        "قدمتها",
        "موسسه",
        "فارنهولت",
        "لمشروع",
        "yep-2021-03",
    ]


def test_tatweel_and_tashkeel_give_the_same_terms() -> None:
    assert lexical_terms(
        "في كم مدرسة عمل برنامج التعليــم الخاص بالفتيات خلال 2021؟"
    ) == lexical_terms("في كم مدرسة عمل برنامج التعليم الخاص بالفتيات خلال 2021؟")
    assert lexical_terms("كَمْ مُتَطَوِّعًا وَمُتَطَوِّعَةً سَانَدُوا المُؤَسَّسَةَ فِي عَامِ 2021؟") == [
        "متطوعا",
        "ومتطوعه",
        "ساندوا",
        "الموسسه",
        "عام",
        "2021",
    ]


def test_english_question() -> None:
    question = "How many people were on the foundation's payroll at the end of 2021?"
    assert lexical_terms(question) == ["people", "foundation", "payroll", "end", "2021"]


def test_mixed_question() -> None:
    question = "What did مؤسسة الريحان للتنمية report for YEP-2021-03 in 2021?"
    assert lexical_terms(question) == [
        "موسسه",
        "الريحان",
        "للتنميه",
        "report",
        "yep-2021-03",
        "2021",
    ]


def test_numbers_attached_to_arabic_letters_become_terms() -> None:
    question = "كم مريضاً حوّلته العيادات المتنقلة إلى المستشفيات بين 2021 و2023؟"
    assert lexical_terms(question) == [
        "مريضا",
        "حولته",
        "العيادات",
        "المتنقله",
        "المستشفيات",
        "2021",
        "2023",
    ]


def test_terms_are_deduplicated_in_order() -> None:
    assert lexical_terms("التعليم ثم التعليم ثم الصحة والتعليم") == ["التعليم", "الصحه", "والتعليم"]


def test_single_letters_are_dropped_but_single_digits_kept() -> None:
    assert lexical_terms("كم طالبة في الصف 3 من مدرسة ب؟") == ["طالبه", "الصف", "3", "مدرسه"]


def test_url_is_one_term() -> None:
    assert lexical_terms("ماذا يذكر التقرير المنشور على https://example.org/r؟") == [
        "يذكر",
        "التقرير",
        "المنشور",
        "https://example.org/r",
    ]


def test_stopwords_with_a_conjunction_are_dropped() -> None:
    assert lexical_terms("وفي عام 2022 فإن الميزانية وكانت أكبر") == [
        "عام",
        "2022",
        "الميزانيه",
        "اكبر",
    ]


def test_stopwords_still_apply_when_teh_marbuta_is_kept() -> None:
    terms = lexical_terms("عدة مدارس في المنطقة", fold_taa_marbuta=False)
    assert terms == ["مدارس", "المنطقة"]
    assert terms[-1].endswith(TEH_MARBUTA)


def test_clitic_variant() -> None:
    question = "ما الذي قدمته المؤسسة للجميع وبالمشروع؟"
    assert lexical_terms(question) == ["قدمته", "الموسسه", "للجميع", "وبالمشروع"]
    # "للجميع" strips to the stopword "جميع", so the variant drops it.
    assert lexical_terms(question, clitics=True) == ["قدمته", "موسسه", "مشروع"]


def test_search_tokens_keep_stopwords_and_split_letters_from_digits() -> None:
    assert search_tokens("في مشروع YEP-2021-03، بين 2021 و2023.") == [
        "في",
        "مشروع",
        "yep-2021-03",
        "بين",
        "2021",
        "و",
        "2023",
    ]


def test_search_tokens_trim_punctuation_after_a_url() -> None:
    assert search_tokens("(انظر https://example.org/r).") == ["انظر", "https://example.org/r"]


def test_stopwords_are_stored_normalised() -> None:
    assert all(normalize_for_search(w) == w for w in ARABIC_STOPWORDS)
    assert all(w == w.lower() for w in ENGLISH_STOPWORDS)


def test_stopword_normalisation_merges_ala_with_the_name_ali() -> None:
    # Documented trade-off: "على" (on) and "علي" (Ali) normalise to the same word.
    assert normalize_for_search("على") == normalize_for_search("علي")
    assert normalize_for_search("علي") in ARABIC_STOPWORDS


@pytest.mark.parametrize(
    ("token", "stem"),
    [
        ("وبالمشروع", "مشروع"),
        ("فبالمشروع", "مشروع"),
        ("والتعليم", "تعليم"),
        ("فالتعليم", "تعليم"),
        ("بالتعليم", "تعليم"),
        ("وللاطفال", "اطفال"),
        ("فللاطفال", "اطفال"),
        ("للتعليم", "تعليم"),
        ("التعليم", "تعليم"),
        ("الطب", "طب"),
    ],
)
def test_strip_clitics(token: str, stem: str) -> None:
    assert strip_clitics(token) == stem


@pytest.mark.parametrize(
    "token",
    ["وادي", "برنامج", "لجنه", "فريق", "تعليم", "الف", "ال", "لله", "", "yep-2021-03", "2021"],
)
def test_strip_clitics_leaves_these_whole(token: str) -> None:
    assert strip_clitics(token) == token


def test_strip_clitics_never_strips_a_seed_word_to_nothing() -> None:
    for line in seed_lines():
        for token in search_tokens(line):
            stem = strip_clitics(token)
            assert len(stem) >= min(len(token), 2), token
            assert token.endswith(stem)
