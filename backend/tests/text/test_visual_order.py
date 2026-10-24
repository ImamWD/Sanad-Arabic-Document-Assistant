"""Visual-order detection and repair.

The S1 extraction spike will add real extractor output here. Until then the cases are
built by hand: a visual-order line is what a reader sees, left to right, when the logical
line is displayed right to left. Arabic runs come out reversed, with brackets in their
mirrored shape; Latin runs and numbers keep their natural order.
"""

import pytest

from sanad.text.arabic import clean_extracted, is_visual_order, repair_visual_order
from tests.text.helpers import BARNAMAJ, ISTIJABA, TAMKEEN, seed_lines

MIRROR = str.maketrans("()[]{}<>«»", ")(][}{><»«")

# (visual, logical) pairs
CASES = [
    (
        "2021 ةيلاملا ةنسلا يف رالود 1,250 غلبمب (Save the Children (UK ةمظنم نم ةحنملا تلصو",
        "وصلت المنحة من منظمة Save the Children (UK) بمبلغ 1,250 دولار في السنة المالية 2021",
    ),
    (
        "YEP-2021-03 عورشملا ةيقافتا يف ةدراولا ةحنملا ةميق ام",
        "ما قيمة المنحة الواردة في اتفاقية المشروع YEP-2021-03",
    ),
    (
        "https://example.org/r ىلع روشنملا يونسلا ريرقتلا يف لماكلا لودجلا",
        "الجدول الكامل في التقرير السنوي المنشور على https://example.org/r",
    ),
    # a flattened table row: two numbers with only a space between them are two runs
    ("790 1,600 بيردتلا اومتأ نيذلا نوبردتملا", "المتدربون الذين أتموا التدريب 1,600 790"),
    ("UNICEF 2021 ريرقت يف ةدراولا ماقرألا", "الأرقام الواردة في تقرير UNICEF 2021"),
    ("نيبردتملا نم 52% تاباشلا ةبسن تغلب", "بلغت نسبة الشابات 52% من المتدربين"),
]


@pytest.mark.parametrize(("visual", "logical"), CASES)
def test_visual_lines_are_repaired(visual: str, logical: str) -> None:
    assert is_visual_order(visual)
    assert repair_visual_order(visual) == logical


@pytest.mark.parametrize(("visual", "logical"), CASES)
def test_logical_lines_are_left_alone(visual: str, logical: str) -> None:
    assert not is_visual_order(logical)
    assert repair_visual_order(logical) == logical


def test_presentation_forms_are_the_strongest_signal() -> None:
    # Neither word ends in teh marbuta, starts with the article or is a stopword, so only
    # the positional glyph shapes tell the two directions apart.
    logical = f"{BARNAMAJ} {TAMKEEN}"
    visual = logical[::-1]
    assert not is_visual_order(logical)
    assert is_visual_order(visual)
    assert clean_extracted([visual]) == ["برنامج تمكين"]


def test_lam_alef_ligature_is_reversed_before_folding() -> None:
    # Folding first would turn the ligature into lam + alef, which the reversal would then
    # swap into "الستجابة"-like garbage.
    assert clean_extracted([ISTIJABA[::-1]]) == ["الاستجابة"]


@pytest.mark.parametrize(
    "line",
    [
        "يونسلا",  # one word: too little evidence
        "Annual Report 2021",  # no Arabic at all
        "2021 340",
        "",
        "ام ةسردملا",  # reversed scores 3, stored scores 1: not more than three times
        "ة و ى",  # single letters carry no evidence
    ],
)
def test_lines_without_enough_evidence_are_left_alone(line: str) -> None:
    assert not is_visual_order(line)
    assert repair_visual_order(line) == line


def test_no_seed_line_is_mistaken_for_visual_order() -> None:
    flagged = [line for line in seed_lines() if is_visual_order(line)]
    assert flagged == []


def test_most_reversed_seed_lines_are_repaired() -> None:
    # Arabic-only lines, so reversing the characters is exactly their visual order. The
    # heuristic is conservative: short headings and table rows often lack the evidence.
    arabic_only = [
        line
        for line in seed_lines()
        if len(line.split()) >= 5
        and not any(c.isdigit() or (c.isascii() and c.isalpha()) for c in line)
    ]
    repaired = [
        line for line in arabic_only if repair_visual_order(line[::-1].translate(MIRROR)) == line
    ]
    assert len(arabic_only) > 400
    assert len(repaired) / len(arabic_only) > 0.95
