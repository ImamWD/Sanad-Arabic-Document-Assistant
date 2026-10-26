"""The real eval sets load, with the mix SYSTEM_DESIGN §11 describes."""

from collections import Counter
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from sanad.eval.cli import REPO_ROOT
from sanad.eval.questions import EvalSetError, SetName, load_set, set_path
from sanad.eval.scoring import has_fact, matching_text

EVAL_DIR = REPO_ROOT / "eval"


def test_headline_set_has_the_documented_mix() -> None:
    eval_set = load_set(set_path(EVAL_DIR, "test"), "test")
    questions = eval_set.questions
    assert len(questions) == 15
    assert Counter(q.expected_outcome for q in questions) == {"answered": 12, "no_answer": 3}
    assert [q.id for q in questions if q.page_split] == ["T14"]
    assert [q.id for q in questions if q.cross_document] == ["T15", "T16"]
    assert Counter(q.language for q in questions) == {"ar": 12, "en": 3}


def test_dev_set_has_thirty_nine_items_and_keeps_former_ids() -> None:
    eval_set = load_set(set_path(EVAL_DIR, "dev"), "dev")
    # 30, plus D31-D36 (R1c's overview and colloquial items) and D37-D39 (R1f's near-misses).
    assert len(eval_set.questions) == 39
    assert [q.id for q in eval_set.questions if q.page_split] == ["D07"]
    formerly = {q.id: q.formerly for q in eval_set.questions if q.formerly}
    assert formerly["D21"] == "T02"
    assert len(formerly) == 10


@pytest.mark.parametrize("name", ["test", "dev"])
def test_every_reference_answer_holds_its_facts(name: SetName) -> None:
    """The matcher on real data. The reference answers write facts as a person would:
    D23 has بُعد with a damma and Arabic-Indic digits, T12 has 140,000 with a separator."""
    eval_set = load_set(set_path(EVAL_DIR, name), name)
    raw = yaml.safe_load(eval_set.path.read_text("utf-8"))["questions"]
    references = {item["id"]: item.get("expected_answer") or "" for item in raw}
    for q in eval_set.questions:
        if q.answerable:
            text = matching_text(references[q.id])
            assert all(has_fact(text, f) for f in q.must_include), q.id


def test_malformed_items_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "questions.yaml"
    path.write_text(
        'set: test\nquestions:\n  - {id: T01, question: "?", expected_outcome: answered}\n',
        "utf-8",
    )
    with pytest.raises(EvalSetError, match="T01 is answerable but lacks facts"):
        load_set(path, "test")
