"""pypdfium2 extraction, paragraph geometry, and the text-layer checks."""

from pathlib import Path

import pytest

from sanad.core.errors import ErrorCode
from sanad.ingest.errors import IngestionError
from sanad.ingest.extract import (
    RawPage,
    _Line,
    check_text_layer,
    extract_pages,
    paragraph_text,
)
from tests.ingest.conftest import BAD, SEED, SEED_ENTRIES, needs_seed_files


def line(text: str, top: float, height: float = 10.0) -> _Line:
    return _Line(text, bottom=top - height, top=top)


def test_lines_with_the_usual_gap_stay_one_paragraph() -> None:
    lines = [line("سطر أول", 700), line("سطر ثانٍ", 686), line("سطر ثالث", 672)]
    assert paragraph_text(lines) == "سطر أول\nسطر ثانٍ\nسطر ثالث"


def test_a_larger_gap_starts_a_paragraph() -> None:
    lines = [line("a", 700), line("b", 686), line("c", 650), line("d", 636), line("e", 622)]
    assert paragraph_text(lines) == "a\nb\n\nc\nd\ne"


def test_a_font_size_change_starts_a_paragraph() -> None:
    lines = [line("عنوان", 720, height=18), line("نص", 698), line("نص", 684)]
    assert paragraph_text(lines) == "عنوان\n\nنص\nنص"


def test_going_back_up_the_page_starts_a_paragraph() -> None:
    lines = [line("left column", 700), line("end", 686), line("right column", 700)]
    assert paragraph_text(lines) == "left column\nend\n\nright column"


def test_lines_without_geometry_are_joined_plainly() -> None:
    assert paragraph_text([_Line("a"), line("b", 700), _Line("")]) == "a\nb\n"
    assert paragraph_text([]) == ""


def raw(text: str, images: int = 0) -> RawPage:
    return RawPage(text=text, images=images)


def test_scans_fail_with_no_text_layer() -> None:
    pages = ["", "", "نص كافٍ على هذه الصفحة لكي تُعدّ صفحة نصية."]
    raws = [raw("", 1), raw("", 1), raw(pages[2])]
    with pytest.raises(IngestionError) as info:
        check_text_layer(pages, raws, min_chars=20, scanned_share=0.5)
    assert info.value.code is ErrorCode.NO_TEXT_LAYER
    assert info.value.params == {"pages": 3, "scanned_pages": 2}


def test_a_few_scanned_pages_are_tolerated() -> None:
    text = "نص كافٍ على هذه الصفحة لكي تُعدّ صفحة نصية."
    check_text_layer([text, "", text], [raw(text), raw("", 1), raw(text)], 20, 0.5)


def test_no_text_and_no_images_is_an_empty_document() -> None:
    with pytest.raises(IngestionError) as info:
        check_text_layer(["", "  12  "], [raw(""), raw("12")], 20, 0.5)
    assert info.value.code is ErrorCode.EMPTY_DOCUMENT


@needs_seed_files
@pytest.mark.parametrize(
    ("fixture", "code"),
    [("truncated.pdf", ErrorCode.FILE_CORRUPT), ("encrypted.pdf", ErrorCode.PDF_ENCRYPTED)],
)
def test_unreadable_pdfs(fixture: str, code: ErrorCode) -> None:
    with pytest.raises(IngestionError) as info:
        extract_pages(BAD / fixture)
    assert info.value.code is code
    assert info.value.params == {}


@needs_seed_files
def test_the_scanned_fixture_has_images_and_no_text() -> None:
    pages = extract_pages(BAD / "scanned-no-text.pdf")
    assert len(pages) == 2
    assert all(p.images >= 1 and not p.text.strip() for p in pages)


@needs_seed_files
def test_a_file_that_is_not_a_pdf_is_corrupt_to_the_parser(tmp_path: Path) -> None:
    with pytest.raises(IngestionError) as info:
        extract_pages(BAD / "not-a-pdf.pdf")
    assert info.value.code is ErrorCode.FILE_CORRUPT


@needs_seed_files
@pytest.mark.parametrize(
    "entry", [e for e in SEED_ENTRIES if e["format"] == "pdf"], ids=lambda e: e["file"]
)
def test_seed_pdfs_extract_one_text_page_per_source_page(entry: dict[str, object]) -> None:
    pages = extract_pages(SEED / "documents" / str(entry["file"]))
    assert len(pages) == entry["page_count"]
    assert all(page.text.strip() for page in pages)
    assert all("￾" not in page.text and "\x02" not in page.text for page in pages)
