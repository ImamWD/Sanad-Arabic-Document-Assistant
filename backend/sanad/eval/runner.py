"""One pass over an eval set: preflight, ask every question, resolve and score each reply.

Pages are matched as `(file, page_number)`, where `file` is the document's
`original_filename`: for seed documents that is the manifest `file` that `expected_citations`
names. Diagnostics candidates carry `file` themselves; citations carry only `document_id`, so
the runner maps ids to files through `GET /api/documents`. The diagnostics contract
(`debug: true`, editors and admins) is in the module docstring of `sanad.eval.cli`.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sanad.eval.client import EVAL_BAD_RESPONSE, AskReply, SanadClient
from sanad.eval.questions import Question
from sanad.eval.scoring import OUTCOMES, CandidatePage, Category, Reply, score_item

# How many candidates of each reply the JSON report keeps: enough for recall@10.
REPORTED_CANDIDATES = 10


@dataclass(frozen=True)
class Row:
    """One question in one run: what was asked, what came back and how it scored."""

    id: str
    language: str
    kinds: list[str]
    page_split: bool
    expected_outcome: str
    outcome: str | None
    band: str | None
    refusal_reason: str | None
    error_code: str | None
    correct: bool
    category: Category | None
    missing_facts: list[str]
    citation_ok: bool
    retrieved: bool | None
    expected_rank: int | None
    top_score: float | None
    cited: list[str]  # "file p<page>", in citation order
    expected: list[str]
    server_ms: int | None  # timings_ms.total from the server, if sent
    wall_ms: int  # measured by the runner
    timings_ms: dict[str, float] = field(default_factory=dict)
    answer: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    # The best-ranked expected page among the candidates: rank, rerank score and the dense and
    # lexical ranks before fusion. What E2 needs to see why a page scored low.
    expected_candidate: dict[str, Any] | None = None
    llm_model: str | None = None


def page_label(file: str | None, page: int | None) -> str:
    return f"{file or '?'} p{page if page is not None else '?'}"


def document_files(documents: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """Document id to file name (`original_filename`)."""
    return {
        str(d["id"]): str(d["original_filename"])
        for d in documents
        if d.get("id") and d.get("original_filename")
    }


def preflight(documents: Sequence[Mapping[str, Any]], questions: Iterable[Question]) -> list[str]:
    """Reasons the stack can't produce a seed-corpus score; empty when it can.

    - The score is defined on the seed corpus (SYSTEM_DESIGN §11), and the reports hold answer
      text, so every document in retrieval scope (not archived) must be a seed document. A
      hosted reference run must never see anything else either.
    - Every expected citation must point at a registered, ready, unarchived seed document;
      otherwise the run would only measure an incomplete ingestion.
    """
    problems: list[str] = []
    non_seed = [d for d in documents if not d.get("is_archived") and not d.get("is_seed")]
    if non_seed:
        problems.append(
            f"{len(non_seed)} non-seed document(s) are in retrieval scope. The eval runs on "
            "the seed corpus only: archive them, or use a stack that holds seed data only."
        )
    seed = {str(d.get("original_filename")): d for d in documents if d.get("is_seed")}
    wanted = sorted({c.file for q in questions for c in q.expected_citations})
    for file in wanted:
        doc = seed.get(file)
        if doc is None:
            problems.append(f"{file}: no seed document with this file name")
        elif doc.get("is_archived"):
            problems.append(f"{file}: archived, so it is out of retrieval")
        elif doc.get("status") != "ready":
            problems.append(f"{file}: status {doc.get('status')!r}, not 'ready'")
    return problems


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _candidates(raw: list[Any], files: Mapping[str, str]) -> tuple[CandidatePage, ...]:
    pages: list[CandidatePage] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        file = item.get("file") or files.get(str(item.get("document_id")))
        page = _int(item.get("page_number", item.get("page")))
        pages.append(
            CandidatePage(
                rank=_int(item.get("rank")) or index + 1,
                file=str(file) if file else None,
                page=page,
                score=_float(item.get("rerank_score", item.get("score"))),
                dense_rank=_int(item.get("dense_rank")),
                lexical_rank=_int(item.get("lexical_rank")),
            )
        )
    return tuple(sorted(pages, key=lambda c: c.rank))


def _diagnostics(data: Mapping[str, Any]) -> Mapping[str, Any]:
    diagnostics = data.get("diagnostics")
    return diagnostics if isinstance(diagnostics, dict) else {}


def timings_of(data: Mapping[str, Any]) -> dict[str, float]:
    """`timings_ms`, inside `diagnostics` or at the top level; numeric values only."""
    raw = _diagnostics(data).get("timings_ms", data.get("timings_ms"))
    if not isinstance(raw, dict):
        return {}
    return {str(k): v for k, raw_v in raw.items() if (v := _float(raw_v)) is not None}


def resolve(reply: AskReply, files: Mapping[str, str]) -> Reply:
    """Turn an HTTP reply into a scoring `Reply`, with document ids resolved to files."""
    data = reply.data
    if data is None:
        return Reply(outcome=None, error_code=reply.error_code)
    outcome = data.get("outcome")
    if outcome not in OUTCOMES:
        return Reply(outcome=None, error_code=EVAL_BAD_RESPONSE)
    cited: list[tuple[str | None, int]] = []
    for cite in data.get("citations") or []:
        page = _int(cite.get("page_number")) if isinstance(cite, dict) else None
        if page is not None:
            cited.append((files.get(str(cite.get("document_id"))), page))
    raw_candidates = _diagnostics(data).get("candidates")
    answer = data.get("answer")
    return Reply(
        outcome=str(outcome),
        band=_str(data.get("band")),
        refusal_reason=_str(data.get("refusal_reason")),
        answer=answer if isinstance(answer, str) else None,
        cited=tuple(cited),
        candidates=_candidates(raw_candidates, files) if isinstance(raw_candidates, list) else None,
        error_code="OUTCOME_ERROR" if outcome == "error" else None,
    )


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _candidate_json(c: CandidatePage) -> dict[str, Any]:
    return {
        "rank": c.rank,
        "page": page_label(c.file, c.page),
        "rerank_score": c.score,
        "dense_rank": c.dense_rank,
        "lexical_rank": c.lexical_rank,
    }


def build_row(question: Question, reply: AskReply, files: Mapping[str, str]) -> Row:
    resolved = resolve(reply, files)
    score = score_item(question, resolved)
    data = reply.data or {}
    timings = timings_of(data)
    total = timings.get("total")
    candidates = resolved.candidates or ()
    diagnostics = _diagnostics(data)
    model = diagnostics.get("llm_model")
    top_score = _float(diagnostics.get("top_score"))
    if top_score is None and candidates:
        top_score = candidates[0].score
    expected = next((c for c in candidates if (c.file, c.page) in question.expected_pages), None)
    return Row(
        id=question.id,
        language=question.language,
        kinds=list(question.kinds),
        page_split=question.page_split,
        expected_outcome=question.expected_outcome,
        outcome=resolved.outcome,
        band=resolved.band,
        refusal_reason=resolved.refusal_reason,
        error_code=resolved.error_code,
        correct=score.correct,
        category=score.category,
        missing_facts=list(score.missing_facts),
        citation_ok=score.citation_ok,
        retrieved=score.retrieved,
        expected_rank=score.expected_rank,
        top_score=top_score,
        cited=[page_label(f, p) for f, p in resolved.cited],
        expected=[page_label(c.file, c.page) for c in question.expected_citations],
        server_ms=round(total) if total is not None else None,
        wall_ms=reply.wall_ms,
        timings_ms=timings,
        answer=resolved.answer,
        candidates=[_candidate_json(c) for c in candidates[:REPORTED_CANDIDATES]],
        expected_candidate=_candidate_json(expected) if expected else None,
        llm_model=str(model) if model else None,
    )


def run_once(
    client: SanadClient,
    questions: Sequence[Question],
    files: Mapping[str, str],
    *,
    debug: bool,
    progress: Callable[[int, Row], None] | None = None,
) -> list[Row]:
    rows: list[Row] = []
    for index, question in enumerate(questions, start=1):
        row = build_row(question, client.ask(question.question, debug=debug), files)
        rows.append(row)
        if progress is not None:
            progress(index, row)
    return rows
