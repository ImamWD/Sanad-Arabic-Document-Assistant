"""Per-page text from a PDF (SYSTEM_DESIGN §5.2 step 3), plus the checks that turn unusable
files into readable failures (step 5).

pypdfium2 always opens the file: it decides FILE_CORRUPT and PDF_ENCRYPTED, the page count
and the images on each page. The text comes from the extractor chosen by PDF_EXTRACTOR:

- `poppler` (default): poppler's `pdftotext -enc UTF-8`, reading-order mode, run as a
  subprocess (poppler is GPL; we never link it). It separates blocks with blank lines. It is
  far more robust on Arabic than pdfium across fonts (C1b: 97.0% of words verbatim on the
  shipped corpus, against pdfium's 95.9%, and 97.5% against 57.7% in Noto Naskh). Known
  limits: with Amiri it splits a word after ر before ي or ب ("الر يحان"), and on fully
  diacritised text it puts tashkeel before its letter.
- `pdfium`: pypdfium2's text. It has no paragraph breaks, so they are rebuilt from
  geometry: a vertical gap clearly larger than the page's usual line gap, a change of font
  size (a heading) or a jump back up the page (a new column or text box) starts a new
  paragraph, written as a blank line.

If pdftotext fails or disagrees with pdfium about the page count, the document falls back to
pdfium's text (logged), so a quirk of one library never loses a document.
"""

from __future__ import annotations

import itertools
import logging
import re
import shutil
import statistics
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
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
PDFTOTEXT = "pdftotext"


class Extractor(StrEnum):
    POPPLER = "poppler"
    PDFIUM = "pdfium"


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


def _poppler_texts(path: Path, pages: int, timeout: float) -> list[str] | None:
    """Per-page text from pdftotext, or None if it can't give exactly `pages` pages."""
    if shutil.which(PDFTOTEXT) is None:
        logger.warning("pdftotext is not installed; using pdfium text")
        return None
    try:
        result = subprocess.run(  # noqa: S603 - fixed argument list, no shell
            [PDFTOTEXT, "-enc", "UTF-8", str(path), "-"],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("pdftotext timed out after %ss; using pdfium text", timeout)
        return None
    # pdftotext ends every page with a form feed, so this is exactly `-f N -l N` per page.
    texts = result.stdout.decode("utf-8", "replace").split("\f")[:-1]
    if result.returncode != 0 or len(texts) != pages:
        logger.warning(
            "pdftotext gave %d pages (exit %s) for %d; using pdfium text",
            len(texts),
            result.returncode,
            pages,
        )
        return None
    return [_LINE_BREAK.sub("\n", text) for text in texts]


def extract_pages(
    path: Path, extractor: Extractor = Extractor.POPPLER, timeout: float = 120
) -> list[RawPage]:
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
            pages = [_page(pdf, i) for i in range(len(pdf))]
        except pdfium.PdfiumError:
            raise IngestionError(ErrorCode.FILE_CORRUPT) from None
    finally:
        pdf.close()
    if extractor is Extractor.POPPLER:
        texts = _poppler_texts(path, len(pages), timeout)
        if texts is not None:
            pages = [replace(page, text=text) for page, text in zip(pages, texts, strict=True)]
    return pages


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
