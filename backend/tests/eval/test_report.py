"""Totals, percentiles, repeats and the report names."""

from dataclasses import replace

import pytest

from sanad.eval.report import (
    aggregate,
    percentile_90,
    report_stem,
    score_line,
    slug,
    spread,
    summarize,
)
from sanad.eval.runner import Row

BASE = Row(
    id="X01",
    language="ar",
    kinds=["factual"],
    page_split=False,
    expected_outcome="answered",
    outcome="answered",
    band="answer",
    refusal_reason=None,
    error_code=None,
    correct=True,
    category=None,
    missing_facts=[],
    citation_ok=True,
    retrieved=True,
    expected_rank=1,
    top_score=0.9,
    cited=["a.pdf p1"],
    expected=["a.pdf p1"],
    server_ms=1000,
    wall_ms=1100,
)


@pytest.mark.parametrize(
    ("values", "p90"),
    [
        ([5.0], 5.0),
        ([1.0, 2.0], 2.0),
        ([float(n) for n in range(1, 11)], 9.0),
        ([3.0, 1.0, 2.0], 3.0),
    ],
)
def test_percentile_90_is_nearest_rank(values: list[float], p90: float) -> None:
    assert percentile_90(values) == p90


def test_spread_of_nothing_is_empty() -> None:
    assert spread([]).n == 0
    assert spread([]).median is None


def test_summary_counts_recall_only_where_candidates_are_known() -> None:
    rows = [
        BASE,
        replace(BASE, id="X02", expected_rank=7, correct=False, category="generation"),
        replace(
            BASE, id="X03", retrieved=False, expected_rank=None, correct=False, category="retrieval"
        ),
        replace(BASE, id="X04", retrieved=None, expected_rank=None, server_ms=None),
        replace(
            BASE,
            id="X05",
            expected_outcome="no_answer",
            outcome="no_answer",
            retrieved=None,
            expected_rank=None,
            timings_ms={"total": 500.0, "rerank": 200.0},
            server_ms=500,
        ),
    ]
    s = summarize(rows)
    assert (s.score, s.total) == (3, 5)
    assert (s.answerable_correct, s.answerable_total) == (2, 4)
    assert (s.refused_correctly, s.unanswerable_total) == (1, 1)
    assert (s.recall["@5"].hits, s.recall["@5"].of) == (1, 3)
    assert (s.recall["@10"].hits, s.recall["@10"].of) == (2, 3)
    assert s.categories == {"retrieval": 1, "generation": 1}
    assert s.server_ms.n == 4
    assert s.stage_ms["rerank"].median == 200.0


def test_error_rows_stay_out_of_the_wall_time() -> None:
    rows = [BASE, replace(BASE, id="X02", correct=False, category="error", wall_ms=900_000)]
    assert summarize(rows).wall_ms.n == 1


def test_score_line_for_one_run_and_for_repeats() -> None:
    wrong = replace(BASE, correct=False, category="generation")
    assert score_line(aggregate([[BASE, BASE]])) == "Score: 2/2"
    agg = aggregate([[BASE, BASE], [BASE, wrong], [wrong, wrong]])
    assert (agg.mean, agg.min, agg.max) == (1.0, 0, 2)
    assert score_line(agg) == "Score: 1.0/2 (range 0-2 over 3 runs)"


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("gemma4:e4b-it-qat", "gemma4-e4b-it-qat"),
        ("Qwen 3.5 / 8B", "qwen-3.5-8b"),
        ("::", "unknown"),
    ],
)
def test_slug(label: str, expected: str) -> None:
    assert slug(label) == expected


def test_report_stem() -> None:
    assert report_stem("20261025T120000Z", "dev", "gemma4:e4b") == "20261025T120000Z-dev-gemma4-e4b"
