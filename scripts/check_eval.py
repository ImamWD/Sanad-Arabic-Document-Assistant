#!/usr/bin/env python3
"""Check the evaluation sets against the rendered seed corpus (C1b).

    python scripts/check_eval.py [--extractor pdfium|poppler] \
        eval/questions.yaml eval/dev_questions.yaml

For every document in the seed manifest it builds the viewer PDF exactly as ingestion will
(SYSTEM_DESIGN §5.2): PDFs as they are, DOCX and TXT through LibreOffice headless (TXT is
decoded first: utf-8, utf-8-sig, then cp1256). It extracts per-page text with the chosen
extractor and checks:

- corpus: every source's front matter equals its manifest entry, every entry carries boolean
  `restricted` and `archived` flags, the viewer PDF has `page_count` pages, and each page
  holds its own source page's text: the opening and closing reliable words of source page N
  are on rendered page N. A negative control proves the check catches a one-page shift.
- eval: every `must_include` fact of an answered item is on its cited page(s), following
  the citation semantics in the YAML headers (seed/README.md §4): by default every fact on
  every listed page; for `cross_document` items each fact on at least one listed page.
  Unanswerable items carry no facts and no citations. No item cites a superseded or
  archived document, and no answered item depends on restricted documents alone.

Facts match after `fold_for_matching` (digits, Arabic separators, tashkeel, tatweel, NFKC,
bidi controls). Numeric facts match as whole numbers, never inside a larger one. Exit
status 0 only when every check passes (100%). Informational lines report extraction
quality (verbatim words, letter-reversed words, lam-alef misses) and extraction speed.

Needs PyYAML, LibreOffice (`--soffice`) and the extractor: pypdfium2, or poppler's
`pdftotext` (`--pdftotext`). It runs in any container that has them (today the `render`
image: `make check-eval`). No network; output names only facts and pages of the synthetic
seed corpus.
"""

# ruff: noqa: S603, T201  -- a CLI tool: it prints its report and runs local converters.
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MARKER = re.compile(r"^<!-- page (\d+) -->[ \t]*$", re.M)
FRONT_MATTER_FIELDS = (
    "doc_id",
    "title_ar",
    "title_en",
    "category",
    "year",
    "programme",
    "language",
    "format",
    "page_count",
    "replaces",
    "encoding",
)
TXT_ENCODINGS = ("utf-8", "utf-8-sig", "cp1256")

# --------------------------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------------------------

TASHKEEL = re.compile("[\u064b-\u0652\u0670]")
TATWEEL = "\u0640"
BIDI_CONTROLS = re.compile("[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]")
# Arabic-Indic and Persian digits, Arabic thousands and decimal separators, Arabic percent.
DIGITS = str.maketrans(
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669"
    "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9"
    "\u066c\u066b\u066a",
    "01234567890123456789,.%",
)
NUMERIC_FACT = re.compile(r"[\d.,]+")


def fold_for_matching(text: str) -> str:
    """Fold text for fact matching: NFKC (presentation forms), bidi controls, tashkeel,
    tatweel, Arabic-Indic/Persian digits and Arabic separators, whitespace.

    TODO(B1): replace with sanad.text.arabic.normalize_number_tokens / normalize_for_search
    once B1 merges. This is eval test tooling only; product code must never import it.
    """
    text = unicodedata.normalize("NFKC", text)
    text = BIDI_CONTROLS.sub("", text)
    text = TASHKEEL.sub("", text).replace(TATWEEL, "")
    text = text.translate(DIGITS)
    return re.sub(r"\s+", " ", text).strip()


def has_fact(page_text: str, fact: str) -> bool:
    """`page_text` is already folded. Numbers match as whole tokens (538 not in 1,538)."""
    f = fold_for_matching(fact)
    if NUMERIC_FACT.fullmatch(f):
        pattern = rf"(?<![\d])(?<![\d][,.]){re.escape(f)}(?![\d])(?![,.]\d)"
        return re.search(pattern, page_text) is not None
    return f in page_text


# --------------------------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------------------------


def source_pages(root: Path, entry: dict[str, object], problems: list[str]) -> list[str]:
    path = root / str(entry["source"])
    text = path.read_text(encoding="utf-8")
    end = text.index("\n---\n", 4)
    front = yaml.safe_load(text[4:end])
    for key in FRONT_MATTER_FIELDS:
        if front.get(key) != entry.get(key):
            problems.append(
                f"{entry['doc_id']}: front matter {key}={front.get(key)!r}, "
                f"manifest {entry.get(key)!r}"
            )
    parts = MARKER.split(text[end + 5 :])
    return [parts[i] for i in range(2, len(parts), 2)]


# Page anchors are letters-only words of three or more letters. Digits, % and separators can
# come out of RTL extraction in another order, so they only anchor pages without usable words.
WORD = re.compile(r"[^\W\d_]{3,}")
TOKEN = re.compile(r"[\w\u064b-\u0652\u0670\u0640]+")
# Extraction of these is renderer- and library-dependent, so they make no reliable anchor:
# - lam-alef, a required ligature (pdfium splits الإلكتروني into "لكتروني الإ")
# - words written with tashkeel: Chromium wraps each base+mark cluster in /ActualText and
#   pdfium reorders letters around it (تسلّمت comes out as "تملست")
LAM_ALEF = re.compile("ل[اأإآ]")


@dataclass
class SourceWords:
    words: list[str]  # every letters-only word, folded
    anchors: list[str]  # reliable ones: no tashkeel, tatweel or lam-alef
    numbers: list[str]


def source_words(markdown: str) -> SourceWords:
    """Words of a source page without its Markdown, folded, plus which can anchor the page."""
    text = re.sub(r"^(#{1,3} |> ?|- |\d+\. )", "", markdown, flags=re.M)
    text = text.replace("**", " ").replace("|", " ")
    words, anchors, numbers = [], [], []
    for raw in TOKEN.findall(text):
        folded = fold_for_matching(raw)
        if WORD.fullmatch(folded):
            words.append(folded)
            if not (TASHKEEL.search(raw) or TATWEEL in raw or LAM_ALEF.search(folded)):
                anchors.append(folded)
        elif folded.isdigit() and len(folded) >= 2:
            numbers.append(folded)
    return SourceWords(words, anchors, numbers)


def page_anchors(src: SourceWords, n: int = 4) -> list[str]:
    """The first and last `n` distinct reliable words of a page; its numbers if it has none."""
    pool = src.anchors if len(src.anchors) >= 2 else src.numbers
    head = list(dict.fromkeys(pool))[:n]
    tail = list(dict.fromkeys(reversed(pool)))[:n]
    return list(dict.fromkeys(head + tail))


def page_drift(source: str, rendered: str) -> list[str] | None:
    """Anchors of a source page missing from a rendered page; None if it has too few."""
    anchors = page_anchors(source_words(source))
    if len(anchors) < 2:
        return None
    return [w for w in anchors if not on_page(w, rendered)]


def on_page(anchor: str, page_text: str) -> bool:
    """Words ignore whitespace (pdfium puts spaces after non-joining letters: و يعمل);
    numbers match whole."""
    if anchor.isdigit():
        return has_fact(page_text, anchor)
    return anchor in page_text.replace(" ", "")


# --------------------------------------------------------------------------------------------
# Viewer PDFs and text extraction
# --------------------------------------------------------------------------------------------


def decode_txt(data: bytes) -> str:
    for encoding in TXT_ENCODINGS:
        try:
            return data.decode(encoding).removeprefix("\ufeff")
        except UnicodeDecodeError:
            continue
    raise ValueError("TXT_ENCODING_UNKNOWN")


def convert(soffice: str, files: list[Path], work: Path, infilter: str | None) -> None:
    """LibreOffice headless to PDF, as ingestion runs it (seed/README.md §6)."""
    if not files:
        return
    cmd = [
        soffice,
        "--headless",
        "--norestore",
        f"-env:UserInstallation=file://{work}/lo-profile",
        *([infilter] if infilter else []),
        "--convert-to",
        "pdf",
        "--outdir",
        str(work),
        *map(str, files),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def viewer_pdfs(
    seed: Path, entries: list[dict[str, object]], work: Path, soffice: str
) -> dict[str, Path]:
    """Manifest file -> the PDF the viewer shows and ingestion extracts."""
    viewer: dict[str, Path] = {}
    docx: list[Path] = []
    txt: list[Path] = []
    for entry in entries:
        file = str(entry["file"])
        path = seed / "documents" / file
        if entry["format"] == "pdf":
            viewer[file] = path
        elif entry["format"] == "docx":
            docx.append(path)
        else:
            utf8 = work / "txt" / file
            utf8.parent.mkdir(exist_ok=True)
            utf8.write_text(decode_txt(path.read_bytes()).replace("\r\n", "\n"), "utf-8")
            txt.append(utf8)
    convert(soffice, docx, work, None)
    convert(soffice, txt, work, "--infilter=Text (encoded):UTF8,LF,,,")
    for path in [*docx, *txt]:
        viewer[path.name] = work / f"{path.stem}.pdf"
    return viewer


def extract_pdfium(pdf_path: Path) -> list[str]:
    import pypdfium2 as pdfium  # only needed for this extractor

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        texts = []
        for index in range(len(pdf)):
            page = pdf[index]
            textpage = page.get_textpage()
            texts.append(textpage.get_text_bounded())
            textpage.close()
            page.close()
        return texts
    finally:
        pdf.close()


def poppler_extractor(pdftotext: str) -> Callable[[Path], list[str]]:
    def extract(pdf_path: Path) -> list[str]:
        # One call per document; pdftotext ends every page with a form feed, so splitting on
        # it gives exactly the per-page text of `-f N -l N`. Reading order mode (no -layout).
        out = subprocess.run(
            [pdftotext, "-enc", "UTF-8", str(pdf_path), "-"],
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8")
        return out.split("\f")[:-1]

    return extract


# --------------------------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------------------------


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    checks: int = 0
    passed: int = 0
    # Informational, not checks: how well the extractor reproduces the source words.
    words: int = 0
    verbatim: int = 0  # found as written on their page
    reversed: int = 0  # not found, but found with their letters reversed
    lam_alef_missed: int = 0  # not found, not reversed, and containing lam-alef

    def check(self, ok: bool, problem: str) -> None:
        self.checks += 1
        if ok:
            self.passed += 1
        else:
            self.problems.append(problem)

    def count_words(self, words: list[str], page_text: str) -> None:
        for word in words:
            self.words += 1
            if word in page_text:
                self.verbatim += 1
            elif word[::-1] in page_text:
                self.reversed += 1
            elif LAM_ALEF.search(word):
                self.lam_alef_missed += 1


def check_corpus(
    root: Path,
    entries: list[dict[str, object]],
    texts: dict[str, list[str]],
    report: Report,
) -> None:
    for entry in entries:
        file = str(entry["file"])
        flags_ok = all(isinstance(entry.get(k), bool) for k in ("restricted", "archived"))
        report.check(flags_ok, f"{file}: manifest needs boolean `restricted` and `archived`")
        expected = int(entry["page_count"])  # type: ignore[arg-type]
        front_problems: list[str] = []
        pages = source_pages(root, entry, front_problems)
        report.check(not front_problems, "; ".join(front_problems))
        report.check(len(pages) == expected, f"{file}: {len(pages)} page markers, {expected=}")
        got = len(texts[file])
        report.check(got == expected, f"{file}: viewer PDF has {got} pages, expected {expected}")
        if got != expected:
            continue
        for number, (source, rendered) in enumerate(zip(pages, texts[file], strict=True), 1):
            missing = page_drift(source, rendered)
            report.check(missing == [], f"{file} p{number}: page text drifted, missing {missing}")
            report.count_words(source_words(source).words, rendered)
        # Negative control: compared with the next page's text, every page must look drifted.
        if expected > 1:
            shifted = texts[file][1:] + texts[file][:1]
            pairs = enumerate(zip(pages, shifted, strict=True), 1)
            blind = [n for n, pair in pairs if page_drift(*pair) == []]
            report.check(not blind, f"{file}: drift check blind to a page shift on pages {blind}")


def check_items(
    path: Path,
    entries: dict[str, dict[str, object]],
    superseded: set[str],
    texts: dict[str, list[str]],
    report: Report,
) -> tuple[int, int]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    items_ok = 0
    items = data["questions"]
    for item in items:
        before = len(report.problems)
        qid = item["id"]
        facts: list[str] = item.get("must_include") or []
        cites: list[dict[str, object]] = item.get("expected_citations") or []
        if item["expected_outcome"] == "no_answer":
            report.check(not facts and not cites, f"{qid}: no_answer item with facts/citations")
        else:
            report.check(bool(facts) and bool(cites), f"{qid}: answered item without facts")
            valid: list[tuple[str, int]] = []
            for cite in cites:
                file, page = str(cite["file"]), int(cite["page"])  # type: ignore[call-overload]
                entry = entries.get(file)
                if entry is None:
                    report.check(False, f"{qid}: cites unknown file {file}")
                    continue
                report.check(
                    entry["doc_id"] not in superseded and not entry.get("archived"),
                    f"{qid}: cites superseded or archived document {file}",
                )
                in_range = 1 <= page <= int(entry["page_count"])  # type: ignore[arg-type]
                report.check(in_range, f"{qid}: {file} has no page {page}")
                if in_range and len(texts[file]) >= page:
                    valid.append((file, page))
            # Viewers and the guest never retrieve restricted documents, so every answered
            # item needs a source they can see.
            open_cites = [f for f, _ in valid if not entries[f].get("restricted")]
            report.check(bool(open_cites), f"{qid}: only restricted documents are cited")
            if "cross_document" in item["kinds"]:
                for fact in facts:
                    found = any(has_fact(texts[f][p - 1], fact) for f, p in valid)
                    report.check(found, f"{qid}: {fact!r} is on none of {fmt_cites(valid)}")
            else:
                for file, page in valid:
                    for fact in facts:
                        report.check(
                            has_fact(texts[file][page - 1], fact),
                            f"{qid}: {fact!r} not on {file} p{page}",
                        )
        if len(report.problems) == before:
            items_ok += 1
    return items_ok, len(items)


def fmt_cites(cites: Iterable[tuple[str, int]]) -> str:
    return ", ".join(f"{f} p{p}" for f, p in cites)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("eval_files", nargs="+", type=Path)
    parser.add_argument(
        "--extractor",
        choices=("pdfium", "poppler"),
        default="pdfium",
        help="per-page text extraction: pypdfium2 or poppler's pdftotext (default: pdfium)",
    )
    parser.add_argument(
        "--seed", type=Path, default=ROOT / "seed", help="seed folder (default: %(default)s)"
    )
    parser.add_argument("--soffice", default="soffice", help="LibreOffice binary")
    parser.add_argument("--pdftotext", default="pdftotext", help="poppler's pdftotext binary")
    args = parser.parse_args()

    seed: Path = args.seed.resolve()
    manifest = json.loads((seed / "manifest.json").read_text(encoding="utf-8"))
    entries: list[dict[str, object]] = manifest["documents"]
    by_file = {str(e["file"]): e for e in entries}
    superseded = {str(e["replaces"]) for e in entries if e.get("replaces")}
    extract = extract_pdfium if args.extractor == "pdfium" else poppler_extractor(args.pdftotext)

    report = Report()
    with tempfile.TemporaryDirectory(prefix="sanad-check-") as tmp:
        try:
            viewer = viewer_pdfs(seed, entries, Path(tmp), args.soffice)
        except FileNotFoundError:
            print(f"check_eval: LibreOffice not found ({args.soffice})", file=sys.stderr)
            return 2
        started = time.perf_counter()
        raw = {file: extract(pdf) for file, pdf in viewer.items()}
        elapsed = time.perf_counter() - started
    texts = {file: [fold_for_matching(t) for t in pages] for file, pages in raw.items()}
    page_total = sum(len(t) for t in texts.values())

    # The manifest's `source` paths are relative to the folder that holds seed/.
    check_corpus(seed.parent, entries, texts, report)
    print(
        f"extractor: {args.extractor}; corpus: {len(entries)} documents, {page_total} pages, "
        f"{report.passed}/{report.checks} checks passed"
    )
    print(
        f"  (info) words: {100.0 * report.verbatim / report.words:.1f}% of {report.words} "
        f"verbatim on their page; {report.reversed} letter-reversed; "
        f"{report.lam_alef_missed} other misses with lam-alef"
    )
    print(f"  (info) extraction: {100 * elapsed / page_total:.2f} s per 100 pages")
    for path in args.eval_files:
        start_checks, start_passed = report.checks, report.passed
        ok, total = check_items(path, by_file, superseded, texts, report)
        print(
            f"{path}: {ok}/{total} items OK, "
            f"{report.passed - start_passed}/{report.checks - start_checks} checks passed"
        )

    for problem in report.problems:
        print(f"FAIL {problem}")
    score = 100.0 * report.passed / report.checks
    print(f"Result: {report.passed}/{report.checks} checks passed ({score:.1f}%)")
    return 0 if report.passed == report.checks else 1


if __name__ == "__main__":
    sys.exit(main())
