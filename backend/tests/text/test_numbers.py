import pytest

from sanad.text.arabic import normalize_for_search, normalize_number_tokens
from tests.text.helpers import arabic_indic, persian_digits

AR_THOUSANDS = "\N{ARABIC THOUSANDS SEPARATOR}"
AR_DECIMAL = "\N{ARABIC DECIMAL SEPARATOR}"
AR_PERCENT = "\N{ARABIC PERCENT SIGN}"


@pytest.mark.parametrize(
    "written",
    [
        arabic_indic(f"1{AR_THOUSANDS}250"),
        "1,250",
        "1250",
        "1\N{THIN SPACE}250",
        "1\N{NARROW NO-BREAK SPACE}250",
        persian_digits("1,250"),
    ],
)
def test_one_number_written_six_ways(written: str) -> None:
    assert normalize_number_tokens(written) == "1250"


def test_millions_and_decimals() -> None:
    assert (
        normalize_number_tokens(arabic_indic(f"5{AR_THOUSANDS}480{AR_THOUSANDS}000")) == "5480000"
    )
    assert normalize_number_tokens("5,480,000") == "5480000"
    assert normalize_number_tokens(arabic_indic(f"12{AR_DECIMAL}5")) == "12.5"
    assert normalize_number_tokens("1,250.75") == "1250.75"


@pytest.mark.parametrize(
    "text",
    [
        "في الأعوام 2019, 2020 و2021",  # a list, not a grouped number
        "معدل 1,25 نقطة",  # the group after the comma isn't three digits
        "الرمز 12345,678",  # the first group is longer than three digits
        "الصفوف 3,4,5",
    ],
)
def test_commas_that_are_not_thousands_separators_stay(text: str) -> None:
    assert normalize_number_tokens(text) == text


@pytest.mark.parametrize(
    "percentage",
    [
        "52%",
        "52 %",
        "%52",
        "% 52",
        arabic_indic("52") + AR_PERCENT,
        AR_PERCENT + arabic_indic("52"),
    ],
)
def test_percent_sign_on_either_side(percentage: str) -> None:
    sentence = f"بلغت نسبة الشابات بين المتدربين {percentage} في 2024"
    assert normalize_number_tokens(sentence) == "بلغت نسبة الشابات بين المتدربين 52% في 2024"


def test_decimal_percentage_flipped_by_extraction() -> None:
    assert normalize_number_tokens("ارتفعت نسبة الالتحاق إلى %61.4 عام 2022") == (
        "ارتفعت نسبة الالتحاق إلى 61.4% عام 2022"
    )


def test_percent_sign_goes_with_the_number_it_touches() -> None:
    assert normalize_number_tokens("من 30% 40 أسرة") == "من 30% 40 أسرة"
    assert normalize_number_tokens("بلغت نسبة الالتحاق في 2021 %52 من الفتيات") == (
        "بلغت نسبة الالتحاق في 2021 52% من الفتيات"
    )
    assert normalize_number_tokens("بلغت نسبة الالتحاق في 2021 % 52 من الفتيات") == (
        "بلغت نسبة الالتحاق في 2021 52% من الفتيات"
    )


def test_letters_case_and_codes_are_untouched() -> None:
    text = arabic_indic(f"أتمّ 1{AR_THOUSANDS}600 متدرب في مشروع YEP-2021-03")
    assert normalize_number_tokens(text) == "أتمّ 1600 متدرب في مشروع YEP-2021-03"


def test_urls_are_untouched() -> None:
    text = "انظر https://example.org/r?ids=1,250&q=%20 حيث 1,250 مستفيداً"
    assert (
        normalize_number_tokens(text)
        == "انظر https://example.org/r?ids=1,250&q=%20 حيث 1250 مستفيداً"
    )


def test_eval_fact_matches_an_answer_in_arabic_digits() -> None:
    # T02 stores the fact as "5,480,000"; a model may answer in Arabic-Indic digits.
    fact = "5,480,000"
    answer = arabic_indic(
        f"أقرّت المؤسسة ميزانية قدرها 5{AR_THOUSANDS}480{AR_THOUSANDS}000 دولار [1]"
    )
    assert normalize_number_tokens(fact) in normalize_number_tokens(answer)
    assert normalize_for_search(fact) in normalize_for_search(answer)
