"""Per-page text from a PDF with pypdfium2 (SYSTEM_DESIGN §5.2 step 3), plus the checks that
turn unusable files into readable failures (step 5).

pdfium returns each page as lines (CRLF-separated) with no paragraph breaks. Chunking is
paragraph-aligned (DECISIONS D1), so paragraph breaks are rebuilt from geometry: a vertical
gap clearly larger than the page's usual line gap, a change of font size (a heading) or a
jump back up the page (a new column or text box) starts a new paragraph, written as a blank
line. The text itself is exactly pdfium's.
"""

from __future__ import annotations

import itertools
import logging
import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from sanad.core.errors import ErrorCode
from sanad.ingest.errors import IngestionError

logger = logging.getLogger(__name__)

# A gap this much larger than the page's usual line gap (in line heights) breaks a paragraph.
PARAGRAPH_GAP = 0.35
# Consecutive lines whose heights differ by more than this ratio are different blocks.
FONT_CHANGE = 1.2
_LINE_BREAK = re.compile(r"\r\n|\r|\n")
# pdfium's marker for a hyphen that ends a line ("long-" / "running"): U+FFFE in its range
# text, U+0002 in its bounded text. Both stand for the hyphen that was printed.
_HYPHEN_MARKS = str.maketrans({"\ufffe": "-", "\x02": "-"})
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class RawPage:
    text: str  # pdfium's text, LF line ends, a blank line between paragraphs
    images: int  # image objects on the page (a scan is an image with no text)


@dataclass(frozen=True)
class _Line:
    text: str
    bottom: float | None = None
    top: float | None = None

    @property
    def height(self) -> float:
        if self.top is None or self.bottom is None:
            return 0.0
        return self.top - self.bottom


def _lines(textpage: pdfium.PdfTextPage) -> list[_Line] | None:
    """Lines with their loose (font-size based) vertical extent; None when the page text
    doesn't map 1:1 onto pdfium's char list (characters outside the BMP), in which case the
    text is kept without paragraph geometry."""
    text = textpage.get_text_range()
    if len(text) != textpage.count_chars():
        return None
    raw = textpage.raw
    lines: list[_Line] = []
    start = 0
    for match in [*_LINE_BREAK.finditer(text), None]:
        end = match.start() if match else len(text)
        bottoms, tops = [], []
        for i in range(start, end):
            if text[i].isspace() or pdfium_c.FPDFText_IsGenerated(raw, i) == 1:
                continue
            _, bottom, _, top = textpage.get_charbox(i, loose=True)
            if top > bottom:
                bottoms.append(bottom)
                tops.append(top)
        if bottoms:
            lines.append(
                _Line(text[start:end], statistics.median(bottoms), statistics.median(tops))
            )
        else:
            lines.append(_Line(text[start:end]))
        start = match.end() if match else len(text)
    return lines


def _similar(a: _Line, b: _Line) -> bool:
    low, high = sorted((a.height, b.height))
    return low > 0 and high / low <= FONT_CHANGE


def paragraph_text(lines: Sequence[_Line]) -> str:
    """Join lines, with a blank line where the geometry says a new paragraph starts."""
    if not lines:
        return ""
    gaps = [
        prev.bottom - line.top
        for prev, line in itertools.pairwise(lines)
        if prev.bottom is not None and line.top is not None and _similar(prev, line)
        if line.top < prev.bottom + prev.height  # going down the page
    ]
    usual = statistics.median(gaps) if gaps else 0.0
    out = [lines[0].text]
    for prev, line in itertools.pairwise(lines):
        out.append("\n\n" if _breaks(prev, line, usual) else "\n")
        out.append(line.text)
    return "".join(out)


def _breaks(prev: _Line, line: _Line, usual_gap: float) -> bool:
    if prev.bottom is None or line.top is None or line.bottom is None:
        return False
    if not _similar(prev, line):
        return True
    height = min(prev.height, line.height)
    if line.top > prev.bottom + height:  # back up the page: a new column or text box
        return True
    return (prev.bottom - line.top) - usual_gap > PARAGRAPH_GAP * height


def _page(pdf: pdfium.PdfDocument, index: int) -> RawPage:
    page = pdf[index]
    try:
        textpage = page.get_textpage()
        try:
            lines = _lines(textpage)
            if lines is None:
                text = _LINE_BREAK.sub("\n", textpage.get_text_bounded())
            else:
                text = paragraph_text(lines)
            text = text.translate(_HYPHEN_MARKS)
        finally:
            textpage.close()
        images = sum(1 for _ in page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,)))
        return RawPage(text=text, images=images)
    finally:
        page.close()


def extract_pages(path: Path) -> list[RawPage]:
    """Every page of the PDF in order; page i + 1 of the viewer is index i."""
    try:
        pdf = pdfium.PdfDocument(str(path))
    except pdfium.PdfiumError as exc:
        if getattr(exc, "err_code", None) == pdfium_c.FPDF_ERR_PASSWORD:
            raise IngestionError(ErrorCode.PDF_ENCRYPTED) from None
        raise IngestionError(ErrorCode.FILE_CORRUPT) from None
    try:
        if len(pdf) == 0:
            raise IngestionError(ErrorCode.FILE_CORRUPT)
        try:
            return [_page(pdf, i) for i in range(len(pdf))]
        except pdfium.PdfiumError:
            raise IngestionError(ErrorCode.FILE_CORRUPT) from None
    finally:
        pdf.close()


def text_chars(text: str) -> int:
    return len(_SPACE.sub("", text))


def check_text_layer(
    cleaned: Sequence[str], raw: Sequence[RawPage], min_chars: int, scanned_share: float
) -> None:
    """NO_TEXT_LAYER for scans (OCR is out of scope), EMPTY_DOCUMENT for files with no text.

    A page is *scanned* when it has fewer than `min_chars` characters of text but carries
    an image; the document is a scan when more than `scanned_share` of its pages are.
    """
    pages = len(cleaned)
    scanned = sum(
        1
        for text, page in zip(cleaned, raw, strict=True)
        if text_chars(text) < min_chars and page.images > 0
    )
    if pages and scanned / pages > scanned_share:
        raise IngestionError(ErrorCode.NO_TEXT_LAYER, pages=pages, scanned_pages=scanned)
    if not any(text_chars(text) >= min_chars for text in cleaned):
        raise IngestionError(ErrorCode.EMPTY_DOCUMENT)
