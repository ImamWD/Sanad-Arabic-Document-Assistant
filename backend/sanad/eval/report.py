"""Totals for a run, the mean and range over repeated runs, and the JSON and Markdown reports.

Reports go to `eval/results/<UTC timestamp>-<set>-<model>.{json,md}`. The JSON holds every
run in full (answers, citations, the top candidates); the Markdown is the readable summary
the README quotes. Nothing is committed unless someone decides to.
"""

import json
import math
import re
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sanad.eval.runner import Row
from sanad.eval.scoring import CATEGORIES

RECALL_AT = (5, 10)

CATEGORY_RULES = (
    "Each failure has one category, the first that applies: `error` (the request failed), "
    "`invented_answer` (an unanswerable question was answered, low confidence included), "
    "`page_split` (a page-split item failed), `false_refusal` (an answerable question was "
    "refused), `retrieval` (no expected page among the candidates), `generation` (an "
    "expected page was retrieved, but the facts or the citation are wrong), `unclassified` "
    "(retrieval or generation, but the server sent no candidates)."
)


@dataclass(frozen=True)
class Spread:
    n: int
    median: float | None
    p90: float | None


@dataclass(frozen=True)
class Recall:
    hits: int
    of: int  # answerable items whose candidates are known


@dataclass(frozen=True)
class RunSummary:
    score: int
    total: int
    answerable_correct: int
    answerable_total: int
    refused_correctly: int
    unanswerable_total: int
    false_refusals: list[str]
    invented_answers: list[str]
    errors: list[str]
    categories: dict[str, int]
    recall: dict[str, Recall]
    server_ms: Spread
    wall_ms: Spread
    stage_ms: dict[str, Spread] = field(default_factory=dict)


@dataclass(frozen=True)
class Aggregate:
    runs: int
    total: int
    scores: list[int]
    mean: float
    min: int
    max: int
    correct_runs: dict[str, int]  # question id: runs in which it was correct


def percentile_90(values: Sequence[float]) -> float:
    """Nearest-rank p90: the smallest value with at least 90% of values at or below it."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)]


def spread(values: Sequence[float]) -> Spread:
    if not values:
        return Spread(0, None, None)
    return Spread(len(values), float(statistics.median(values)), float(percentile_90(values)))


def summarize(rows: Sequence[Row]) -> RunSummary:
    answerable = [r for r in rows if r.expected_outcome == "answered"]
    unanswerable = [r for r in rows if r.expected_outcome != "answered"]
    known = [r for r in answerable if r.retrieved is not None]
    recall = {
        f"@{k}": Recall(
            hits=sum(1 for r in known if r.expected_rank is not None and r.expected_rank <= k),
            of=len(known),
        )
        for k in RECALL_AT
    }
    categories: dict[str, int] = {
        c: n for c in CATEGORIES if (n := sum(1 for r in rows if r.category == c))
    }
    stage_keys = sorted({k for r in rows for k in r.timings_ms if k != "total"})
    return RunSummary(
        score=sum(1 for r in rows if r.correct),
        total=len(rows),
        answerable_correct=sum(1 for r in answerable if r.correct),
        answerable_total=len(answerable),
        refused_correctly=sum(1 for r in unanswerable if r.correct),
        unanswerable_total=len(unanswerable),
        false_refusals=[r.id for r in rows if r.category == "false_refusal"],
        invented_answers=[r.id for r in rows if r.category == "invented_answer"],
        errors=[r.id for r in rows if r.category == "error"],
        categories=categories,
        recall=recall,
        server_ms=spread([r.server_ms for r in rows if r.server_ms is not None]),
        wall_ms=spread([r.wall_ms for r in rows if r.category != "error"]),
        stage_ms={
            k: spread([r.timings_ms[k] for r in rows if k in r.timings_ms]) for k in stage_keys
        },
    )


def aggregate(runs: Sequence[Sequence[Row]]) -> Aggregate:
    scores = [sum(1 for r in rows if r.correct) for rows in runs]
    correct_runs: dict[str, int] = {}
    for rows in runs:
        for r in rows:
            correct_runs[r.id] = correct_runs.get(r.id, 0) + int(r.correct)
    return Aggregate(
        runs=len(runs),
        total=len(runs[0]) if runs else 0,
        scores=scores,
        mean=statistics.fmean(scores) if scores else 0.0,
        min=min(scores, default=0),
        max=max(scores, default=0),
        correct_runs=correct_runs,
    )


def score_line(agg: Aggregate) -> str:
    """The last line the run prints: `Score: X/N`, or the mean and range over repeats."""
    if agg.runs == 1:
        return f"Score: {agg.scores[0]}/{agg.total}"
    return f"Score: {agg.mean:.1f}/{agg.total} (range {agg.min}-{agg.max} over {agg.runs} runs)"


def slug(label: str) -> str:
    """A file-name-safe form of a label: gemma4:e4b-it-qat becomes gemma4-e4b-it-qat."""
    return re.sub(r"[^a-z0-9._-]+", "-", label.lower()).strip("-.") or "unknown"


def report_stem(timestamp: str, set_name: str, model: str) -> str:
    return f"{timestamp}-{set_name}-{slug(model)}"


def write_reports(
    results_dir: Path,
    stem: str,
    metadata: Mapping[str, Any],
    runs: Sequence[Sequence[Row]],
) -> tuple[Path, Path]:
    results_dir.mkdir(parents=True, exist_ok=True)
    summaries = [summarize(rows) for rows in runs]
    agg = aggregate(runs)
    document = {
        "metadata": dict(metadata),
        "score": score_line(agg).removeprefix("Score: "),
        "aggregate": asdict(agg),
        "category_rules": CATEGORY_RULES,
        "runs": [
            {"summary": asdict(s), "questions": [asdict(r) for r in rows]}
            for s, rows in zip(summaries, runs, strict=True)
        ],
    }
    json_path = results_dir / f"{stem}.json"
    md_path = results_dir / f"{stem}.md"
    json_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", "utf-8")
    md_path.write_text(render_markdown(metadata, runs, summaries, agg), "utf-8")
    return json_path, md_path


# --- Markdown -------------------------------------------------------------------------------


def _seconds(ms: float | None) -> str:
    return "n/a" if ms is None else f"{ms / 1000:.1f} s"


def _spread(s: Spread) -> str:
    if not s.n:
        return "n/a"
    return f"median {_seconds(s.median)}, p90 {_seconds(s.p90)} (n={s.n})"


def _ids(ids: Sequence[str]) -> str:
    return f"{len(ids)} ({', '.join(ids)})" if ids else "0"


def _recall(s: RunSummary) -> str:
    at5, at10 = s.recall["@5"], s.recall["@10"]
    if not at5.of:
        return "recall@5 and recall@10: n/a (the server sent no candidates)"
    return (
        f"recall@5: {at5.hits}/{at5.of}; recall@10: {at10.hits}/{at10.of} "
        "(an expected page among the candidates)"
    )


def _cell(value: object) -> str:
    text = "-" if value is None or value == "" or value == [] else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _duration(seconds: float) -> str:
    minutes, secs = divmod(round(seconds), 60)
    return f"{minutes} min {secs} s" if minutes else f"{secs} s"


def _failure_detail(r: Row) -> str:
    parts: list[str] = []
    if r.error_code:
        parts.append(f"error {r.error_code}")
    if r.outcome:
        parts.append(f"outcome {r.outcome}")
    if r.refusal_reason:
        parts.append(f"refusal_reason {r.refusal_reason}")
    if r.band:
        parts.append(f"band {r.band}")
    if r.top_score is not None:
        parts.append(f"top score {r.top_score:.3f}")
    if r.missing_facts:
        parts.append("missing facts " + ", ".join(r.missing_facts))
    if r.expected_outcome == "answered" and r.outcome in ("answered", "low_confidence"):
        parts.append("citation ok" if r.citation_ok else "no expected page cited")
    if r.retrieved is not None:
        rank = f"best expected rank {r.expected_rank}" if r.expected_rank else "not retrieved"
        parts.append(rank)
    return "; ".join(parts)


def _run_section(title: str, rows: Sequence[Row]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| ID | Lang | Kinds | Outcome | Correct | Category | Cited pages | Expected pages "
        "| Rank | Latency |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        latency = r.server_ms if r.server_ms is not None else r.wall_ms
        lines.append(
            "| "
            + " | ".join(
                _cell(v)
                for v in (
                    r.id,
                    r.language,
                    ", ".join(r.kinds + (["page_split"] if r.page_split else [])),
                    r.outcome or r.error_code,
                    "yes" if r.correct else "no",
                    r.category,
                    ", ".join(r.cited),
                    ", ".join(r.expected),
                    r.expected_rank,
                    _seconds(latency),
                )
            )
            + " |"
        )
    failures = [r for r in rows if not r.correct]
    lines += ["", "Failures:", ""]
    lines += [f"- **{r.id}** `{r.category}`: {_failure_detail(r)}" for r in failures] or ["- none"]
    return [*lines, ""]


def render_markdown(
    metadata: Mapping[str, Any],
    runs: Sequence[Sequence[Row]],
    summaries: Sequence[RunSummary],
    agg: Aggregate,
) -> str:
    first = summaries[0]
    invented = sorted({i for s in summaries for i in s.invented_answers})
    lines = [
        f"# Eval: {metadata.get('set')} set, {metadata.get('model')}",
        "",
        f"**{score_line(agg)}**",
        "",
    ]
    if invented:
        lines += [
            f"> **INVENTED ANSWERS: {len(invented)} ({', '.join(invented)}).** The system "
            "answered a question the documents can't answer. This is the failure the refusal "
            "gate exists to prevent.",
            "",
        ]
    errors = sorted({i for s in summaries for i in s.errors})
    if errors:
        lines += [
            f"> **Request errors: {_ids(errors)}.** Those items count as wrong; the score "
            "is not a clean measurement.",
            "",
        ]
    lines += ["| | |", "|---|---|"]
    lines += [f"| {_cell(k)} | {_cell(v)} |" for k, v in metadata.items()]
    lines += ["", "## Totals", ""]
    if agg.runs > 1:
        lines.append(f"- Scores over {agg.runs} runs: {', '.join(map(str, agg.scores))}")
    for index, s in enumerate(summaries, start=1):
        prefix = f"Run {index}: " if agg.runs > 1 else ""
        cats = ", ".join(f"{k} {v}" for k, v in s.categories.items()) or "none"
        lines += [
            f"- {prefix}Score: {s.score}/{s.total}",
            f"- {prefix}Answerable correct: {s.answerable_correct}/{s.answerable_total}",
            f"- {prefix}Refusal accuracy: {s.refused_correctly}/{s.unanswerable_total} "
            f"unanswerable refused; false refusals: {_ids(s.false_refusals)}",
            f"- {prefix}Invented answers: {_ids(s.invented_answers)}",
            f"- {prefix}{_recall(s)}",
            f"- {prefix}Latency, server total: {_spread(s.server_ms)}",
            f"- {prefix}Latency, request wall time: {_spread(s.wall_ms)}",
            f"- {prefix}Failures by category: {cats}",
        ]
        for key, stage in s.stage_ms.items():
            lines.append(f"- {prefix}Stage `{key}`: {_spread(stage)}")
    if "wall_seconds" in metadata:
        lines.append(f"- Run wall time: {_duration(float(metadata['wall_seconds']))}")
    if first.recall["@5"].of == 0 and first.answerable_total:
        lines.append(
            "- Warning: no diagnostics came back, so recall is unknown and retrieval and "
            "generation failures are `unclassified`."
        )
    lines.append("")
    for index, rows in enumerate(runs, start=1):
        title = f"Questions, run {index}" if agg.runs > 1 else "Questions"
        lines += _run_section(title, rows)
    if agg.runs > 1:
        lines += ["## Correct in how many runs", "", "| ID | Correct |", "|---|---|"]
        lines += [f"| {q} | {n}/{agg.runs} |" for q, n in agg.correct_runs.items()]
        lines.append("")
    lines += ["## Category rules", "", CATEGORY_RULES, ""]
    return "\n".join(lines)
