#!/usr/bin/env python3
"""Check the evaluation sets against the rendered seed corpus (C1b).

    python scripts/check_eval.py eval/questions.yaml eval/dev_questions.yaml

For every document in seed/manifest.json it builds the viewer PDF exactly as ingestion will
(SYSTEM_DESIGN §5.2): PDFs as they are, DOCX and TXT through LibreOffice headless. It
extracts per-page text with pypdfium2 and checks:

- corpus: every source's front matter equals its manifest entry, the viewer PDF has
  `page_count` pages, and each page holds its own source page's text: the opening and
  closing words of source page N are on rendered page N.
- eval: every `must_include` fact of an answered item is on its cited page(s), following
  the citation semantics in the YAML headers (seed/README.md §4): by default every fact on
  every listed page; for `cross_document` items each fact on at least one listed page.
  Unanswerable items carry no facts and no citations, and no item cites a superseded
  document.

Facts match after folding digits (Latin, Arabic-Indic, Persian), Arabic separators,
diacritics, tatweel, presentation forms and bidi controls. Numeric facts match as whole
numbers, never inside a larger one. Exit status 0 only when everything passes (100%).

Needs pypdfium2, PyYAML and LibreOffice (`soffice`). No network, no document text leaves
the machine; output lists facts and page numbers of the synthetic seed corpus only.
"""

# ruff: noqa: S603, T201  -- a CLI tool: it prints its report and runs LibreOffice locally.
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pypdfium2 as pdfium
import yaml

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "seed"
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

# How ingestion turns DOCX and TXT into the PDF that defines their page numbers. TXT is
# decoded in Python first (LibreOffice can't detect Windows-1256) and handed over as UTF-8.
LIBREOFFICE = [
    "soffice",
    "--headless",
    "--norestore",
    "-env:UserInstallation=file:///tmp/sanad-check-lo",
]
TXT_INFILTER = "--infilter=Text (encoded):UTF8,LF,,,"
TXT_ENCODINGS = ("utf-8", "utf-8-sig", "cp1256")

# --------------------------------------------------------------------------------------------
# Normalisation
# TODO(B1): switch to sanad.text.arabic once it is merged (CLAUDE.md rule 5). This local fold
# mirrors the B1 spec for search normalisation, limited to what fact matching needs.
# --------------------------------------------------------------------------------------------

TASHKEEL = re.compile("[ً-ْٰ]")
TATWEEL = "ـ"
BIDI_CONTROLS = re.compile("[؜‎‏‪-‮⁦-⁩]")
# Arabic-Indic and Persian digits, Arabic thousands and decimal separators, Arabic percent.
DIGITS = str.maketrans(
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669"
    "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9"
    "\u066c\u066b\u066a",
    "01234567890123456789,.%",
)
NUMERIC_FACT = re.compile(r"[\d.,]+")


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = BIDI_CONTROLS.sub("", text)
    text = TASHKEEL.sub("", text).replace(TATWEEL, "")
    text = text.translate(DIGITS)
    return re.sub(r"\s+", " ", text).strip()


def has_fact(page_text: str, fact: str) -> bool:
    """`page_text` is already folded. Numbers match as whole tokens (538 not in 1,538)."""
    f = fold(fact)
    if NUMERIC_FACT.fullmatch(f):
        pattern = rf"(?<![\d])(?<![\d][,.]){re.escape(f)}(?![\d])(?![,.]\d)"
        return re.search(pattern, page_text) is not None
    return f in page_text


# --------------------------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------------------------


def source_pages(entry: dict[str, object], problems: list[str]) -> list[str]:
    path = ROOT / str(entry["source"])
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
        folded = fold(raw)
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


def on_page(anchor: str, page_text: str) -> bool:
    """Words ignore whitespace (pdfium puts spaces after non-joining letters: و يعمل);
    numbers match whole."""
    if anchor.isdigit():
        return has_fact(page_text, anchor)
    return anchor in page_text.replace(" ", "")


# --------------------------------------------------------------------------------------------
# Viewer PDFs and text
# --------------------------------------------------------------------------------------------


def decode_txt(data: bytes) -> str:
    for encoding in TXT_ENCODINGS:
        try:
            return data.decode(encoding).removeprefix("﻿")
        except UnicodeDecodeError:
            continue
    raise ValueError("TXT_ENCODING_UNKNOWN")


def convert(files: list[Path], work: Path, infilter: str | None) -> None:
    if not files:
        return
    cmd = [*LIBREOFFICE, *([infilter] if infilter else []), "--convert-to", "pdf"]
    subprocess.run(
        [*cmd, "--outdir", str(work), *map(str, files)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def viewer_pdfs(entries: list[dict[str, object]], work: Path) -> dict[str, Path]:
    """Manifest file -> the PDF the viewer shows and ingestion extracts."""
    viewer: dict[str, Path] = {}
    docx: list[Path] = []
    txt: list[Path] = []
    for entry in entries:
        file = str(entry["file"])
        path = SEED / "documents" / file
        if entry["format"] == "pdf":
            viewer[file] = path
        elif entry["format"] == "docx":
            docx.append(path)
        else:
            utf8 = work / "txt" / file
            utf8.parent.mkdir(exist_ok=True)
            utf8.write_text(decode_txt(path.read_bytes()).replace("\r\n", "\n"), "utf-8")
            txt.append(utf8)
    convert(docx, work, None)
    convert(txt, work, TXT_INFILTER)
    for path in [*docx, *txt]:
        viewer[path.name] = work / f"{path.stem}.pdf"
    return viewer


def page_texts(pdf_path: Path) -> list[str]:
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        texts = []
        for index in range(len(pdf)):
            page = pdf[index]
            textpage = page.get_textpage()
            texts.append(fold(textpage.get_text_bounded()))
            textpage.close()
            page.close()
        return texts
    finally:
        pdf.close()


# --------------------------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------------------------


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    checks: int = 0
    passed: int = 0
    # Informational, not a check: source words found verbatim on their extracted page.
    fidelity_words: int = 0
    fidelity_found: int = 0

    def check(self, ok: bool, problem: str) -> None:
        self.checks += 1
        if ok:
            self.passed += 1
        else:
            self.problems.append(problem)


def check_corpus(
    entries: list[dict[str, object]], texts: dict[str, list[str]], report: Report
) -> None:
    for entry in entries:
        file = str(entry["file"])
        expected = int(entry["page_count"])  # type: ignore[arg-type]
        front_problems: list[str] = []
        pages = source_pages(entry, front_problems)
        report.check(not front_problems, "; ".join(front_problems))
        report.check(len(pages) == expected, f"{file}: {len(pages)} page markers, {expected=}")
        got = len(texts[file])
        report.check(got == expected, f"{file}: viewer PDF has {got} pages, expected {expected}")
        if got != expected:
            continue
        for number, (source, rendered) in enumerate(zip(pages, texts[file], strict=True), 1):
            words = source_words(source)
            anchors = page_anchors(words)
            missing = [w for w in anchors if not on_page(w, rendered)]
            report.check(
                len(anchors) >= 2 and not missing,
                f"{file} p{number}: page text drifted, missing {missing} of {anchors}",
            )
            report.fidelity_words += len(words.words)
            report.fidelity_found += sum(w in rendered for w in words.words)


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
                    entry["doc_id"] not in superseded,
                    f"{qid}: cites superseded document {file}",
                )
                in_range = 1 <= page <= int(entry["page_count"])  # type: ignore[arg-type]
                report.check(in_range, f"{qid}: {file} has no page {page}")
                if in_range and len(texts[file]) >= page:
                    valid.append((file, page))
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
    args = parser.parse_args()

    if shutil.which("soffice") is None:
        print("check_eval: LibreOffice (soffice) is not in this container", file=sys.stderr)
        return 2

    manifest = json.loads((SEED / "manifest.json").read_text(encoding="utf-8"))
    entries: list[dict[str, object]] = manifest["documents"]
    by_file = {str(e["file"]): e for e in entries}
    superseded = {str(e["replaces"]) for e in entries if e.get("replaces")}

    report = Report()
    with tempfile.TemporaryDirectory(prefix="sanad-check-") as tmp:
        viewer = viewer_pdfs(entries, Path(tmp))
        texts = {file: page_texts(pdf) for file, pdf in viewer.items()}

    check_corpus(entries, texts, report)
    corpus_checks, corpus_passed = report.checks, report.passed
    print(
        f"corpus: {len(entries)} documents, {sum(len(t) for t in texts.values())} pages, "
        f"{corpus_passed}/{corpus_checks} checks passed"
    )
    fidelity = 100.0 * report.fidelity_found / report.fidelity_words
    print(
        f"  (info) {fidelity:.1f}% of {report.fidelity_words} source words extract verbatim "
        "on their page with pypdfium2"
    )
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
