"""`python -m sanad.eval` end to end against the fake API: every category in one run, the
report files and their metadata, repeats, filters and the preflight."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from sanad.core.config import Settings
from sanad.eval import cli
from tests.eval.fakes import FakeSanad, Scripted, answer, http_error, refuse, seed_document

AR21 = "annual-report-2021.pdf"
AR20 = "annual-report-2020.pdf"
GEP15 = "gep-enrolment-survey-2015.pdf"
GEP20 = "gep-midterm-evaluation-2020.pdf"
WB17 = "wash-baseline-survey-2017.pdf"
WF21 = "wash-final-evaluation-2021.pdf"
CHP24 = "chp-evaluation-2024.pdf"
FILES = (AR21, AR20, GEP15, GEP20, WB17, WF21, CHP24)


def item(
    qid: str, text: str, facts: list[str], cites: list[tuple[str, int]], **extra: Any
) -> dict[str, Any]:
    return {
        "id": qid,
        "language": "ar",
        "kinds": extra.pop("kinds", ["factual", "numeric"]),
        "question": text,
        "must_include": facts,
        "expected_citations": [{"file": f, "page": p} for f, p in cites],
        "expected_outcome": "answered" if facts else "no_answer",
        **extra,
    }


ITEMS = [
    item("A01", "كم شاباً حصل على عمل في 2021؟", ["538"], [(AR21, 6)]),
    item("A02", "ما أكثر سبب لترك البنات المدرسة؟", ["بعد المدرسة"], [(GEP15, 3)]),
    item(
        "A03",
        "كيف تغيرت نسبة المياه الآمنة؟",
        ["41", "78"],
        [(WB17, 3), (WF21, 2)],
        kinds=["cross_document", "temporal", "numeric"],
    ),
    item("A04", "What enrolment rate was reached in 2022?", [], [], kinds=["unanswerable"]),
    item("A05", "كم متدرباً أنهى البرنامج؟", ["820"], [(AR20, 6)]),
    item("A06", "في كم مدرسة عمل البرنامج؟", ["36"], [(AR21, 9)]),
    item("A07", "كم مدرسة شملها المشروع؟", ["36"], [(AR21, 9)]),
    item("A08", "كم حالة أحيلت؟", ["1,840"], [(CHP24, 5)], page_split=True),
    item("A09", "هل يسمح بالعمل من المنزل؟", [], [], kinds=["unanswerable"]),
    item("A10", "كم متطوعاً ساند المؤسسة؟", ["340"], [(AR21, 3)]),
]
SCRIPT: dict[str, Any] = {
    ITEMS[0]["question"]: answer("التحق ٥٣٨ شاباً وشابة [1]", (AR21, 6)),
    ITEMS[1]["question"]: answer("بُعد المدرسة عن السكن [1]", (GEP15, 3)),
    ITEMS[2]["question"]: answer(
        "من 41% [1] إلى 78% [2]", (WB17, 3), (AR20, 1), candidates=[(WB17, 3), (AR20, 1)]
    ),
    ITEMS[3]["question"]: answer("It reached 68% [1].", (GEP20, 4)),
    ITEMS[4]["question"]: refuse("gate", [(AR20, 2)]),
    ITEMS[5]["question"]: answer("820 متدرباً [1]", (AR20, 6)),
    ITEMS[6]["question"]: answer("30 مدرسة [1]", (AR21, 9)),
    ITEMS[7]["question"]: refuse("sentinel", [(CHP24, 4)]),
    ITEMS[8]["question"]: refuse("gate", [(AR20, 2)]),
    ITEMS[9]["question"]: http_error(503, "LLM_UNAVAILABLE"),
}
HEALTH = {
    "status": "ok",
    "db": "ok",
    "ml": "ok",
    "llm_provider": "ollama",
    "llm_model": "gemma4:e4b-it-qat",
    "ollama_version": "0.40.10",
}


@pytest.fixture
def eval_dir(tmp_path: Path) -> Path:
    write_set(tmp_path / "eval", ITEMS)
    return tmp_path / "eval"


def write_set(directory: Path, items: list[dict[str, Any]], name: str = "test") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    file = "questions.yaml" if name == "test" else "dev_questions.yaml"
    body = {"set": name, "version": 2, "questions": items}
    # JSON is valid YAML, and keeps PyYAML out of the test's typing.
    (directory / file).write_text(json.dumps(body, ensure_ascii=False), "utf-8")


def fake(**kwargs: Any) -> FakeSanad:
    documents = kwargs.pop("documents", [seed_document(f) for f in FILES])
    return FakeSanad(kwargs.pop("script", SCRIPT), documents, **kwargs)


def run(fake_api: FakeSanad, eval_dir: Path, *args: str) -> int:
    argv = ["--set", "test", "--eval-dir", str(eval_dir), "--git-sha", "abc123", *args]
    return cli.main(argv, transport=fake_api.transport)


def report(eval_dir: Path) -> tuple[dict[str, Any], str]:
    (json_path,) = (eval_dir / "results").glob("*.json")
    md = json_path.with_suffix(".md").read_text("utf-8")
    return json.loads(json_path.read_text("utf-8")), md


def last_line(out: str) -> str:
    return out.rstrip("\n").splitlines()[-1]


def test_full_run_scores_and_categorises_every_item(
    eval_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api = fake(health=HEALTH)
    code = run(api, eval_dir, "--hardware", "M5 MacBook, CPU")

    out = capsys.readouterr()
    assert last_line(out.out) == "Score: 4/10"
    assert "INVENTED ANSWERS on A04" in out.out
    assert "request errors on A10" in out.err
    assert code == 1  # a request failed, so the score is flagged as not clean
    assert all(body["debug"] is True for body in api.asked)

    data, md = report(eval_dir)
    rows = {r["id"]: r for r in data["runs"][0]["questions"]}
    assert {qid: r["category"] for qid, r in rows.items()} == {
        "A01": None,
        "A02": None,
        "A03": None,
        "A04": "invented_answer",
        "A05": "false_refusal",
        "A06": "retrieval",
        "A07": "generation",
        "A08": "page_split",
        "A09": None,
        "A10": "error",
    }
    assert rows["A05"]["refusal_reason"] == "gate"
    assert rows["A07"]["missing_facts"] == ["36"]
    assert rows["A07"]["expected_candidate"]["dense_rank"] == 3
    assert rows["A05"]["expected_candidate"] is None
    assert rows["A10"]["error_code"] == "LLM_UNAVAILABLE"
    assert rows["A01"]["cited"] == [f"{AR21} p6"]
    assert rows["A01"]["expected"] == [f"{AR21} p6"]

    summary = data["runs"][0]["summary"]
    assert summary["score"] == 4
    assert summary["invented_answers"] == ["A04"]
    assert summary["false_refusals"] == ["A05"]
    assert (summary["refused_correctly"], summary["unanswerable_total"]) == (1, 2)
    # A01, A02, A03 and A07 had an expected page among 7 known candidate lists (A10 failed).
    assert summary["recall"]["@5"] == {"hits": 4, "of": 7}
    assert summary["server_ms"]["median"] == 1200.0

    meta = data["metadata"]
    assert meta["git_sha"] == "abc123"
    assert meta["model"] == "gemma4:e4b-it-qat"  # from /api/health
    assert meta["hardware"] == "M5 MacBook, CPU"
    assert meta["ollama_version"] == "0.40.10"
    assert meta["set"] == "test"
    assert meta["signed_in_as"] == "editor (editor@sanad.example)"
    assert meta["date"].endswith("+00:00")
    assert data["score"] == "4/10"

    assert "**Score: 4/10**" in md
    assert "INVENTED ANSWERS: 1 (A04)" in md
    assert "recall@5: 4/7" in md
    assert "| A06 | ar | factual, numeric | answered | no | retrieval |" in md
    assert "**A05** `false_refusal`: outcome no_answer; refusal_reason gate" in md
    assert "no expected page among the candidates" in md
    a07 = "best expected page at rank 1 (rerank 0.850, dense rank 3, lexical rank -)"
    assert a07 in md
    # Gate refusals (A05, A09) send null LLM timings, so only the 7 generations count.
    assert "Stage `generate`: median 0.5 s, p90 0.9 s (n=7)" in md
    assert chr(0x2014) not in md  # owner rule: no em dash, not even as an empty cell


def test_report_file_name_has_timestamp_set_and_model(eval_dir: Path) -> None:
    run(fake(script=dict(SCRIPT)), eval_dir, "--model", "gemma4:e4b-it-qat", "--only", "A01")
    (path,) = (eval_dir / "results").glob("*.json")
    stamp, set_name, model = path.stem.split("-", 2)
    assert len(stamp) == 16 and stamp.endswith("Z")
    assert (set_name, model) == ("test", "gemma4-e4b-it-qat")
    assert path.with_suffix(".md").is_file()


def test_clean_run_exits_zero_and_falls_back_to_probed_metadata(
    eval_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run(fake(), eval_dir, "--only", "A01,A09")
    assert code == 0
    assert last_line(capsys.readouterr().out) == "Score: 2/2"
    data, _ = report(eval_dir)
    meta = data["metadata"]
    assert meta["questions"] == 2
    assert meta["only"] == "A01,A09"
    assert meta["ollama_version"] == "0.40.10"  # asked Ollama itself
    assert meta["model"] == "fake-model"  # from the diagnostics
    assert meta["hardware"].startswith("unlabelled (")
    assert meta["server_llm_provider"] == "unknown"


def test_unreachable_ollama_leaves_the_version_unknown(eval_dir: Path) -> None:
    run(fake(ollama_version=None), eval_dir, "--only", "A01")
    data, _ = report(eval_dir)
    assert data["metadata"]["ollama_version"] == "unknown"


def test_flags_win_over_the_api(eval_dir: Path) -> None:
    run(fake(health=HEALTH), eval_dir, "--only", "A01", "--model", "m", "--ollama-version", "9")
    meta = report(eval_dir)[0]["metadata"]
    assert (meta["model"], meta["ollama_version"]) == ("m", "9")


def test_repeat_reports_mean_and_range(eval_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    def flaky(attempt: int) -> Scripted:
        right = answer("التحق 538 شاباً [1]", (AR21, 6))
        return right if attempt % 2 else answer("التحق 540 شاباً [1]", (AR21, 6))

    script = dict(SCRIPT)
    script[ITEMS[0]["question"]] = flaky
    code = run(fake(script=script), eval_dir, "--only", "A01,A09", "--repeat", "3")

    assert code == 0
    assert last_line(capsys.readouterr().out) == "Score: 1.7/2 (range 1-2 over 3 runs)"
    data, md = report(eval_dir)
    assert data["aggregate"]["scores"] == [2, 1, 2]
    assert data["aggregate"]["correct_runs"] == {"A01": 2, "A09": 3}
    assert len(data["runs"]) == 3
    assert "| A01 | 2/3 |" in md
    assert "## Questions, run 3" in md


def test_viewer_gets_no_diagnostics_and_failures_stay_unclassified(
    eval_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api = fake()
    run(api, eval_dir, "--as", "viewer", "--only", "A06,A07")
    assert last_line(capsys.readouterr().out) == "Score: 0/2"
    assert all("debug" not in body for body in api.asked)
    data, md = report(eval_dir)
    rows = data["runs"][0]["questions"]
    assert [r["category"] for r in rows] == ["unclassified", "unclassified"]
    assert data["runs"][0]["summary"]["recall"]["@10"] == {"hits": 0, "of": 0}
    assert "recall@5 and recall@10: n/a" in md
    assert "Warning: no diagnostics came back" in md


def test_guest_signs_in_without_a_password(eval_dir: Path) -> None:
    assert run(fake(), eval_dir, "--as", "guest", "--only", "A01") == 0
    assert report(eval_dir)[0]["metadata"]["signed_in_as"] == "guest (guest)"


def test_preflight_failure_stops_before_the_first_question(
    eval_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docs = [seed_document(f) for f in FILES if f != CHP24]
    docs.append(seed_document("client-upload.pdf", is_seed=False))
    api = fake(documents=docs)

    assert run(api, eval_dir) == 1
    err = capsys.readouterr().err
    assert "non-seed document" in err
    assert f"{CHP24}: no seed document" in err
    assert api.asked == []
    assert not (eval_dir / "results").exists()


def test_refused_sign_in_stops_the_run(
    eval_dir: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    wrong = Settings(demo_editor_password=SecretStr("not-the-password"))
    monkeypatch.setattr(cli, "get_settings", lambda: wrong)
    api = fake()
    assert run(api, eval_dir) == 1
    assert "INVALID_CREDENTIALS" in capsys.readouterr().err
    assert api.asked == []


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--only", "A01,Z99"], "unknown question ids Z99"),
        (["--set", "dev"], "dev_questions.yaml"),
    ],
)
def test_bad_command_line_exits_two(
    eval_dir: Path, capsys: pytest.CaptureFixture[str], args: list[str], message: str
) -> None:
    assert run(fake(), eval_dir, *args) == 2
    assert message in capsys.readouterr().err


def test_set_name_must_match_the_file(eval_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_set(eval_dir, ITEMS[:1], name="test")
    (eval_dir / "dev_questions.yaml").write_text(
        (eval_dir / "questions.yaml").read_text("utf-8"), "utf-8"
    )
    assert run(fake(), eval_dir, "--set", "dev") == 2
    assert "set is 'test', expected 'dev'" in capsys.readouterr().err


def test_repeat_must_be_positive(eval_dir: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        run(fake(), eval_dir, "--repeat", "0")
    assert exit_info.value.code == 2
