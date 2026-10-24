from sanad.text.arabic import clean_extracted, normalize_for_search
from tests.text.helpers import BARNAMAJ, ISTIJABA, TAMKEEN, arabic_indic

HEADER = "مؤسسة الريحان للتنمية — التقرير السنوي 2021"
BODIES = [
    "## مقدمة\n\nيغطي هذا التقرير عام 2021، وهو العام الأول من المرحلة الثانية.",
    "## أبرز الأرقام\n\nأتمّ 1,600 شاب وشابة التدريب المهني خلال العام.",
    "## الصحة المجتمعية\n\nقدّمت العيادات المتنقلة 12,400 استشارة طبية في سهول النخيل.",
    "## المياه والصرف الصحي\n\nأُنجزت 42 نقطة مياه آمنة في قرى الهضبة الشرقية.",
]


def test_one_string_per_page_empty_pages_included() -> None:
    assert clean_extracted(["", "مقدمة التقرير", "  \n\t\n "]) == ["", "مقدمة التقرير", ""]
    assert clean_extracted([]) == []


def test_presentation_forms_and_lam_alef_fold() -> None:
    page = f"{BARNAMAJ} {TAMKEEN}\n{ISTIJABA} الطارئة"
    assert clean_extracted([page]) == ["\n".join(["برنامج تمكين", "الاستجابة الطارئة"])]


def test_bidi_controls_and_byte_order_marks_are_removed() -> None:
    page = (
        "\N{ZERO WIDTH NO-BREAK SPACE}\N{RIGHT-TO-LEFT EMBEDDING}مشروع "
        "\N{LEFT-TO-RIGHT ISOLATE}YEP-2021-03\N{POP DIRECTIONAL ISOLATE}"
        "\N{POP DIRECTIONAL FORMATTING}\N{RIGHT-TO-LEFT MARK}"
    )
    assert clean_extracted([page]) == ["مشروع YEP-2021-03"]


def test_codes_urls_digits_and_case_stay_byte_exact() -> None:
    line = arabic_indic(
        "يمكن الاطلاع على تقرير المشروع YEP-2021-03 عبر https://example.org/R?id=7 وفيه "
        "1\N{ARABIC THOUSANDS SEPARATOR}600 متدرب بنسبة 52\N{ARABIC PERCENT SIGN}"
    )
    assert clean_extracted([line]) == [line]


def test_superscript_footnote_markers_are_kept() -> None:
    line = "بلغ عدد المستفيدين 2,950 أسرة\N{SUPERSCRIPT ONE}"
    assert clean_extracted([line]) == [line]


def test_thin_space_thousands_separator_survives_cleaning() -> None:
    thin, narrow = "\N{THIN SPACE}", "\N{NARROW NO-BREAK SPACE}"
    line = f"بلغ عدد المستفيدين 1{thin}250 أسرة و12{narrow}400 استشارة"
    cleaned = clean_extracted([line])
    assert cleaned == [line]
    assert normalize_for_search(cleaned[0]) == "بلغ عدد المستفيدين 1250 اسره و 12400 استشاره"
    # Anywhere else a thin space is just a space.
    assert clean_extracted([f"عام 2021{thin}{thin}مشروع 1{thin}25 نقطة{narrow}"]) == [
        "عام 2021 مشروع 1 25 نقطة"
    ]


def test_whitespace_collapses_and_paragraphs_survive() -> None:
    lines = [
        "",
        "  يغطي هذا التقرير \t\t عام 2024،\N{NO-BREAK SPACE}وهو عام انتقالي.  ",
        "في مسيرة البرنامج.",
        "",
        "  \t",
        "",
        "  ويعرض التقرير نتائج التدريب.",
        "",
        "",
    ]
    assert clean_extracted(["\n".join(lines)]) == [
        "\n".join(
            [
                "يغطي هذا التقرير عام 2024، وهو عام انتقالي.",
                "في مسيرة البرنامج.",
                "",
                "ويعرض التقرير نتائج التدريب.",
            ]
        )
    ]


def test_running_header_and_page_numbers_are_removed() -> None:
    # The header varies only in tatweel and digit style; the footer is the page number.
    headers = [HEADER, "مؤسسة الريحـــان للتنمية — التقرير السنوي ٢٠٢١", HEADER, HEADER]
    pages = [
        f"{header}\n{body}\n\n{arabic_indic(f'صفحة {n} من 4')}"
        for n, (header, body) in enumerate(zip(headers, BODIES, strict=True), start=1)
    ]
    assert clean_extracted(pages) == BODIES


def test_page_numbers_may_start_anywhere_and_blank_pages_do_not_count() -> None:
    pages = ["", *(f"{body}\n- {n} -" for n, body in enumerate(BODIES[:3], start=12))]
    assert clean_extracted(pages) == ["", *BODIES[:3]]


def test_page_that_is_only_header_and_footer_becomes_empty() -> None:
    pages = [f"{HEADER}\n{body}\nسري — للاستخدام الداخلي" for body in BODIES[:3]]
    pages.append(f"{HEADER}\nسري — للاستخدام الداخلي")
    assert clean_extracted(pages) == [*BODIES[:3], ""]


def test_a_bare_number_next_to_a_bare_page_number_stays() -> None:
    # Page 2 ends with a table cell "790" and then its page number "2": both mask to "#".
    # Only the lines that count with the page go, and the ambiguous page keeps both.
    pages = [f"{body}\n{n}" for n, body in enumerate(BODIES, start=1)]
    pages[1] = f"{BODIES[1]}\n| الملتحقون بسوق العمل |\n790\n2"
    cleaned = clean_extracted(pages)
    assert cleaned[0] == BODIES[0]
    assert cleaned[1] == pages[1]
    assert cleaned[2:] == BODIES[2:]


def test_lines_on_half_the_pages_or_fewer_stay() -> None:
    pages = [f"{HEADER}\n{body}" if n % 2 else body for n, body in enumerate(BODIES)]
    assert clean_extracted(pages) == pages


def test_documents_with_fewer_than_three_pages_are_untouched() -> None:
    pages = [f"{HEADER}\n{body}" for body in BODIES[:2]]
    assert clean_extracted(pages) == pages
    assert clean_extracted([HEADER]) == [HEADER]


def test_repeated_table_rows_with_changing_totals_stay() -> None:
    totals = ["1,600", "2,450", "980"]
    pages = [
        f"{body}\n| **المجموع** | {total} |" for body, total in zip(BODIES, totals, strict=False)
    ]
    assert clean_extracted(pages) == pages


def test_repeated_lines_in_the_middle_of_a_page_stay() -> None:
    middle = "الجدول التالي يلخص النتائج حسب المحافظة:"
    pages = [
        "\n".join(
            [
                f"## برنامج {name}",
                f"بدأ برنامج {name} عام 2015.",
                f"يعمل برنامج {name} في ثلاث محافظات.",
                middle,
                f"تراجعت تكاليف برنامج {name} في 2021.",
                f"يتابع فريق الرصد مؤشرات برنامج {name}.",
                f"انتهى عرض نتائج برنامج {name}.",
            ]
        )
        for name in ("التعليم", "الصحة المجتمعية", "المياه")
    ]
    assert clean_extracted(pages) == pages


def test_visual_order_lines_are_repaired() -> None:
    visual = "2021 ةيلاملا ةنسلا يف رالود 1,250 غلبمب (Save the Children (UK ةمظنم نم ةحنملا تلصو"
    logical = "وصلت المنحة من منظمة Save the Children (UK) بمبلغ 1,250 دولار في السنة المالية 2021"
    assert clean_extracted([f"## الإيرادات\n{visual}"]) == [f"## الإيرادات\n{logical}"]
