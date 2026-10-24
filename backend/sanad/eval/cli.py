"""`python -m sanad.eval --set test|dev`: score a running stack, end to end over HTTP.

    docker compose run --rm backend-dev python -m sanad.eval --set test \
        [--base-url http://api:8000] [--as editor] [--model LABEL] [--hardware LABEL] \
        [--ollama-version V] [--git-sha SHA] [--repeat N] [--only T04,T09]

`make eval` and `make eval-dev` run it with the git sha filled in. Steps:
1. `GET /api/health`, then sign in (the demo editor by default; its password comes from
   `DEMO_EDITOR_PASSWORD`, as for `python -m sanad.init`).
2. Preflight on `GET /api/documents`: seed documents only in retrieval scope, and every
   expected citation's file registered and ready (see `sanad.eval.runner.preflight`).
3. `POST /api/ask` for each question, one at a time, with `debug: true` for editors and
   admins. Scoring: `sanad.eval.scoring`.
4. Reports in eval/results/. The last line printed is `Score: X/N`.

Diagnostics contract (R1, editors and admins, only with `debug: true`):

    "diagnostics": {
      "candidates": [{"rank": 1, "document_id": "<uuid>", "page_number": 6, "score": 0.83}],
      "timings_ms": {"total": 34210, ...},
      "llm_model": "..."
    }

`candidates` are all reranked candidates, best first, on refusals too. Also accepted: `file`
for `document_id`, `page` for `page_number`, `rerank_score` for `score`, and `timings_ms` at
the top level. Without diagnostics, recall is reported as n/a.

Exit status: 0 when the run completed (whatever the score), 1 when the stack can't be used
or a request failed during the run, 2 for a bad command line or eval set.
"""

import argparse
import os
import platform
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2

from sanad.core.config import get_settings
from sanad.core.security import Role
from sanad.eval.client import EvalClientError, SanadClient
from sanad.eval.questions import SET_FILES, EvalSetError, Question, load_set, set_path
from sanad.eval.report import aggregate, report_stem, score_line, write_reports
from sanad.eval.runner import Row, document_files, preflight, run_once
from sanad.init import demo_accounts

REPO_ROOT = Path(__file__).resolve().parents[3]
PRINCIPALS = ("editor", "admin", "viewer", "guest")
DIAGNOSTICS_ROLES = ("editor", "admin")
UNKNOWN = "unknown"


def emit(line: str = "", *, err: bool = False) -> None:
    stream = sys.stderr if err else sys.stdout
    stream.write(line + "\n")
    stream.flush()


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m sanad.eval", description=__doc__.split("\n\n")[0] if __doc__ else None
    )
    parser.add_argument("--set", required=True, choices=tuple(SET_FILES), dest="set_name")
    parser.add_argument("--base-url", default="http://api:8000", help="default: %(default)s")
    parser.add_argument(
        "--as",
        dest="principal",
        choices=PRINCIPALS,
        default="editor",
        help="demo account to sign in as (default: %(default)s; diagnostics need editor+)",
    )
    parser.add_argument("--model", help="model label for the report (default: from the API)")
    parser.add_argument("--hardware", help="hardware label, e.g. 'M5 MacBook, CPU, 8 GB stack'")
    parser.add_argument("--ollama-version", help="default: from /api/health or Ollama itself")
    parser.add_argument("--ollama-url", default="http://ollama:11434", help="default: %(default)s")
    parser.add_argument("--git-sha", default=UNKNOWN, help="commit under test (make eval sets it)")
    parser.add_argument("--repeat", type=int, default=1, help="runs, for mean and range")
    parser.add_argument("--only", help="comma-separated question ids, e.g. T04,T09")
    parser.add_argument("--timeout", type=float, default=900.0, help="seconds per question")
    parser.add_argument("--eval-dir", type=Path, default=REPO_ROOT / "eval")
    parser.add_argument("--results-dir", type=Path, help="default: <eval-dir>/results")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    return args


def select_questions(questions: Sequence[Question], only: str | None) -> list[Question]:
    if not only:
        return list(questions)
    wanted = [q.strip() for q in only.split(",") if q.strip()]
    known = {q.id for q in questions}
    unknown = [q for q in wanted if q not in known]
    if unknown:
        raise EvalSetError(f"--only: unknown question ids {', '.join(unknown)}")
    return [q for q in questions if q.id in wanted]


def sign_in(client: SanadClient, principal: str) -> str:
    """Sign in as a demo account; returns its email."""
    if principal == "guest":
        client.login_guest()
        return "guest"
    role = Role(principal)
    account = next(a for a in demo_accounts(get_settings()) if a.role is role and not a.is_guest)
    if account.password is None:
        raise EvalClientError(f"{account.email} has no demo password")
    client.login(account.email, account.password.get_secret_value())
    return account.email


def default_hardware() -> str:
    return (
        f"unlabelled ({platform.machine()}, {os.cpu_count()} CPUs seen by the eval container; "
        "pass --hardware)"
    )


def progress_printer(run: int, runs: int, total: int) -> Callable[[int, Row], None]:
    prefix = f"run {run}/{runs} " if runs > 1 else ""

    def show(index: int, row: Row) -> None:
        verdict = "correct" if row.correct else f"WRONG {row.category}"
        latency = row.server_ms if row.server_ms is not None else row.wall_ms
        emit(
            f"{prefix}[{index}/{total}] {row.id} {row.outcome or row.error_code} "
            f"{verdict} {latency / 1000:.1f} s"
        )

    return show


def main(argv: Sequence[str] | None = None, transport: httpx2.BaseTransport | None = None) -> int:
    args = parse_args(argv)
    try:
        eval_set = load_set(set_path(args.eval_dir, args.set_name), args.set_name)
        questions = select_questions(eval_set.questions, args.only)
    except (OSError, EvalSetError) as exc:
        emit(f"eval: {exc}", err=True)
        return 2

    started_at = datetime.now(UTC)
    started = time.perf_counter()
    runs: list[list[Row]] = []
    with SanadClient(args.base_url, timeout=args.timeout, transport=transport) as client:
        try:
            health = client.health()
            email = sign_in(client, args.principal)
            documents = client.documents()
        except EvalClientError as exc:
            emit(f"eval: {exc}", err=True)
            return 1
        problems = preflight(documents, questions)
        if problems:
            emit("eval: the stack is not ready for a seed-corpus run:", err=True)
            for problem in problems:
                emit(f"  - {problem}", err=True)
            return 1
        files = document_files(documents)
        ollama = (
            args.ollama_version
            or health.get("ollama_version")
            or client.ollama_version(args.ollama_url)
            or UNKNOWN
        )
        debug = args.principal in DIAGNOSTICS_ROLES
        emit(f"eval: {len(questions)} questions from {eval_set.path.name}, as {email}")
        for run in range(1, args.repeat + 1):
            show = progress_printer(run, args.repeat, len(questions))
            runs.append(run_once(client, questions, files, debug=debug, progress=show))
    wall_seconds = time.perf_counter() - started

    first_model = next((r.llm_model for rows in runs for r in rows if r.llm_model), None)
    model = args.model or health.get("llm_model") or first_model or UNKNOWN
    try:
        set_file = str(eval_set.path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        set_file = str(eval_set.path)
    metadata: dict[str, Any] = {
        "set": eval_set.name,
        "set_file": set_file,
        "set_version": eval_set.version,
        "questions": len(questions),
        "only": args.only or "-",
        "date": started_at.isoformat(timespec="seconds"),
        "git_sha": args.git_sha,
        "model": str(model),
        "hardware": args.hardware or default_hardware(),
        "ollama_version": str(ollama),
        "server_llm_provider": health.get("llm_provider") or UNKNOWN,
        "server_llm_model": health.get("llm_model") or UNKNOWN,
        "signed_in_as": f"{args.principal} ({email})",
        "diagnostics_requested": debug,
        "base_url": args.base_url,
        "runs": args.repeat,
        "wall_seconds": round(wall_seconds, 1),
    }
    stem = report_stem(started_at.strftime("%Y%m%dT%H%M%SZ"), eval_set.name, str(model))
    results_dir = args.results_dir or args.eval_dir / "results"
    json_path, md_path = write_reports(results_dir, stem, metadata, runs)

    agg = aggregate(runs)
    invented = sorted({r.id for rows in runs for r in rows if r.category == "invented_answer"})
    errors = sorted({r.id for rows in runs for r in rows if r.category == "error"})
    emit(f"eval: reports {json_path} and {md_path}")
    if invented:
        emit(f"eval: INVENTED ANSWERS on {', '.join(invented)}")
    if errors:
        emit(f"eval: request errors on {', '.join(errors)}; the score is not clean", err=True)
    emit(score_line(agg))
    return 1 if errors else 0
