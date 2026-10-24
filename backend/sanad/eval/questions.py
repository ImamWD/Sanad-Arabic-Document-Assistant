"""Load an eval set (eval/questions.yaml or eval/dev_questions.yaml) and check its shape.

The YAML headers define the conventions. The ones scoring depends on:
- `expected_citations` lists `(file, page)` pairs: the manifest `file` (the rendered file
  name) and the source page number, which is the viewer PDF page.
- Scoring accepts any one listed citation. For `cross_document` items each fact sits on at
  least one listed page rather than on all of them, which matters to the reader of a failure,
  not to the score.
- `page_split: true` marks a fact in a paragraph that crosses a page break.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]  # PyYAML ships no type information

SetName = Literal["test", "dev"]
SET_FILES: dict[SetName, str] = {"test": "questions.yaml", "dev": "dev_questions.yaml"}
EXPECTED_OUTCOMES = ("answered", "no_answer")


class EvalSetError(ValueError):
    """The eval set file is malformed; the message names the item."""


@dataclass(frozen=True)
class ExpectedCitation:
    file: str
    page: int


@dataclass(frozen=True)
class Question:
    id: str
    language: str
    kinds: tuple[str, ...]
    question: str
    must_include: tuple[str, ...]
    expected_citations: tuple[ExpectedCitation, ...]
    expected_outcome: str  # answered | no_answer
    page_split: bool = False
    formerly: str | None = None

    @property
    def answerable(self) -> bool:
        return self.expected_outcome == "answered"

    @property
    def cross_document(self) -> bool:
        return "cross_document" in self.kinds

    @property
    def expected_pages(self) -> frozenset[tuple[str, int]]:
        return frozenset((c.file, c.page) for c in self.expected_citations)


@dataclass(frozen=True)
class EvalSet:
    name: str
    version: int
    path: Path
    questions: tuple[Question, ...]


def set_path(eval_dir: Path, name: SetName) -> Path:
    return eval_dir / SET_FILES[name]


def load_set(path: Path, expected_name: str | None = None) -> EvalSet:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise EvalSetError(f"{path}: expected a mapping with a `questions` list")
    name = str(data.get("set", ""))
    if expected_name is not None and name != expected_name:
        raise EvalSetError(f"{path}: set is {name!r}, expected {expected_name!r}")
    questions = tuple(_question(item, path) for item in data["questions"])
    ids = [q.id for q in questions]
    if len(set(ids)) != len(ids):
        raise EvalSetError(f"{path}: duplicate question ids")
    return EvalSet(name=name, version=int(data.get("version", 0)), path=path, questions=questions)


def _question(item: Any, path: Path) -> Question:
    if not isinstance(item, dict) or not item.get("id"):
        raise EvalSetError(f"{path}: an item has no id")
    qid = str(item["id"])
    outcome = item.get("expected_outcome")
    if outcome not in EXPECTED_OUTCOMES:
        raise EvalSetError(f"{path}: {qid} has expected_outcome {outcome!r}")
    facts = tuple(str(f) for f in item.get("must_include") or [])
    cites = tuple(
        ExpectedCitation(file=str(c["file"]), page=int(c["page"]))
        for c in item.get("expected_citations") or []
    )
    if outcome == "answered" and not (facts and cites):
        raise EvalSetError(f"{path}: {qid} is answerable but lacks facts or citations")
    if outcome == "no_answer" and (facts or cites):
        raise EvalSetError(f"{path}: {qid} is unanswerable but has facts or citations")
    question = str(item.get("question") or "").strip()
    if not question:
        raise EvalSetError(f"{path}: {qid} has no question")
    return Question(
        id=qid,
        language=str(item.get("language", "")),
        kinds=tuple(str(k) for k in item.get("kinds") or []),
        question=question,
        must_include=facts,
        expected_citations=cites,
        expected_outcome=str(outcome),
        page_split=bool(item.get("page_split", False)),
        formerly=str(item["formerly"]) if item.get("formerly") else None,
    )
