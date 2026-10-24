"""The ask pipeline as a stream of events (SYSTEM_DESIGN §6). `POST /ask` and `POST /ask/stream`
run the same code; the JSON endpoint keeps only `final` (or `error`).

Events, in order:
- `stage` queued (only when every generation slot is busy as the question arrives), with the
  number of generations ahead;
- `stage` searching;
- `stage` reading, with the number of excerpts and the band. The amber banner shows from here;
- `eta` (skipped on a refusal: nothing will be generated);
- `stage` writing, with the first token that is released (see sanad.llm.holdback);
- `token`, many;
- `final`: the validated answer, which replaces the streamed text.

A gate refusal goes from `reading` straight to `final`, never calling the LLM. A sentinel
refusal emits no `writing` and no `token`. A `no_valid_citation` refusal may have streamed text,
which `final` (outcome no_answer, answer null) replaces. Discarded text is never stored.
"""

import logging
import time
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from sanad.core.errors import ErrorCode
from sanad.core.models import Language, User
from sanad.llm.base import Done, HostedNonSeedDataError, LlmProvider, LlmUnavailableError
from sanad.llm.eta import expected_seconds
from sanad.llm.holdback import SentinelHoldback
from sanad.llm.prompts import Excerpt, build_prompt
from sanad.llm.queue import GenerationQueue
from sanad.llm.settings import LlmSettings
from sanad.llm.validate import RefusalReason, Validated, validate
from sanad.retrieval.gate import Band, band_for
from sanad.retrieval.ml import MlUnavailableError
from sanad.retrieval.settings import RetrievalSettings
from sanad.retrieval.types import (
    Candidate,
    CitationRecord,
    Filters,
    Outcome,
    PerfRecord,
    QueryRecord,
    QueryStore,
    Retrieved,
    Retriever,
)
from sanad.text.arabic import detect_language

logger = logging.getLogger(__name__)

# The HTTP status `POST /ask` answers with for each error the pipeline can end in.
ERROR_STATUS: dict[ErrorCode, int] = {
    ErrorCode.SEARCH_UNAVAILABLE: 503,
    ErrorCode.LLM_UNAVAILABLE: 503,
    ErrorCode.HOSTED_LLM_NON_SEED_DATA: 503,
}


@dataclass(frozen=True)
class Event:
    name: str  # stage | eta | token | final | error
    data: dict[str, Any]

    @property
    def status(self) -> int:
        """For an `error` event: the HTTP status of the JSON endpoint."""
        code = ErrorCode(self.data["error"]["code"]) if self.name == "error" else None
        return ERROR_STATUS.get(code, 500) if code else 200


def _stage(stage: str, **extra: Any) -> Event:
    return Event("stage", {"stage": stage, **extra})


def _error(code: ErrorCode) -> Event:
    return Event("error", {"error": {"code": code.value, "params": {}}})


@dataclass(frozen=True)
class AskInput:
    user: User
    session_id: str | None
    question: str
    filters: Filters = field(default_factory=Filters)
    # Add `diagnostics` to `final` (the eval's retrieval and timing view). The route decides who
    # may ask for it; the stream never does.
    debug: bool = False


def question_language(question: str, user: User) -> str:
    """The question's own language; the user's UI language when it can't tell (mixed)."""
    detected = detect_language(question)
    if detected in (Language.AR, Language.EN):
        return detected
    return Language(user.preferred_language).value


def snippet(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat.rfind(" ", 0, limit)
    return flat[: cut if cut > limit // 2 else limit].rstrip() + "…"


def diagnostics(
    retrieved: Retrieved,
    band: Band,
    llm_model: str,
    done: Done | None,
    total_ms: int,
) -> dict[str, Any]:
    """Every reranked candidate with its ranks and scores, the band and the step timings. Ids,
    positions and scores only: never chunk text."""
    timings = retrieved.timings_ms
    return {
        "candidates": [
            {
                "rank": rank,
                "document_id": str(c.document_id),
                "file": c.file,
                "page_number": c.page_number,
                "chunk_id": str(c.chunk_id),
                "rerank_score": c.score,
                "dense_rank": c.dense_rank,
                "lexical_rank": c.lexical_rank,
            }
            for rank, c in enumerate(retrieved.candidates, start=1)
        ],
        "top_score": retrieved.top_score,
        "band": band.value,
        "timings_ms": {
            "embed": timings.get("embed"),
            "retrieve": timings.get("retrieve"),
            "rerank": timings.get("rerank"),
            "first_token": done.prompt_ms if done else None,
            "generate": done.prompt_ms + done.output_ms if done else None,
            "total": total_ms,
        },
        "llm_model": llm_model,
    }


def nearest_documents(candidates: Sequence[Candidate], limit: int) -> list[Candidate]:
    """The best candidate of each distinct document, best first."""
    seen: dict[uuid.UUID, Candidate] = {}
    for c in candidates:
        if c.document_id not in seen and len(seen) < limit:
            seen[c.document_id] = c
    return list(seen.values())


class AskPipeline:
    def __init__(
        self,
        *,
        retriever: Retriever,
        store: QueryStore,
        provider: LlmProvider,
        queue: GenerationQueue,
        retrieval: RetrievalSettings,
        llm: LlmSettings,
    ) -> None:
        self._retriever = retriever
        self._store = store
        self._provider = provider
        self._queue = queue
        self._rs = retrieval
        self._ls = llm

    def _final_payload(
        self,
        query_id: uuid.UUID,
        outcome: Outcome,
        band: Band,
        validated: Validated,
        context: Sequence[Candidate],
        nearest: Sequence[Candidate],
    ) -> dict[str, Any]:
        cited = [context[n - 1] for n in validated.cited]
        return {
            "query_id": str(query_id),
            "outcome": outcome.value,
            "band": band.value,
            "refusal_reason": validated.refusal.value if validated.refusal else None,
            "answer": validated.answer,
            "citations": [
                {
                    "rank": rank,
                    "document_id": str(c.document_id),
                    "title": c.title,
                    "page_number": c.page_number,
                    "snippet": snippet(c.text, self._rs.snippet_chars),
                    "char_start": c.char_start,
                    "char_end": c.char_end,
                    "file_type": c.file_type,
                    "is_converted": c.is_converted,
                }
                for rank, c in enumerate(cited, start=1)
            ],
            "nearest_documents": [
                {"document_id": str(c.document_id), "title": c.title} for c in nearest
            ],
        }

    async def run(self, ask: AskInput) -> AsyncIterator[Event]:
        started = time.monotonic()
        language = question_language(ask.question, ask.user)

        def elapsed_ms() -> int:
            return round((time.monotonic() - started) * 1000)

        def record(**fields: Any) -> QueryRecord:
            return QueryRecord(
                user_id=ask.user.id,
                session_id=ask.session_id,
                question=ask.question,
                language=language,
                filters=ask.filters.as_json(),
                latency_ms=elapsed_ms(),
                **fields,
            )

        ahead = self._queue.ahead()
        if ahead:
            yield _stage("queued", position=ahead)
        yield _stage("searching")
        try:
            retrieved: Retrieved = await self._retriever.retrieve(
                ask.user, ask.question, ask.filters
            )
        except MlUnavailableError:
            logger.warning("ask: ml service unavailable", exc_info=True)
            await self._store.save(
                record(
                    outcome=Outcome.ERROR,
                    band=None,
                    refusal_reason=None,
                    answer=None,
                    top_score=None,
                    error_code=ErrorCode.SEARCH_UNAVAILABLE.value,
                )
            )
            yield _error(ErrorCode.SEARCH_UNAVAILABLE)
            return

        top = retrieved.top_score
        band = band_for(top, self._rs.t_refuse, self._rs.t_confident)
        context = [] if band is Band.REFUSE else retrieved.candidates[: self._rs.retrieval_top_k]
        nearest = nearest_documents(retrieved.candidates, self._rs.nearest_documents)
        yield _stage("reading", sources=len(context), band=band.value)

        if band is Band.REFUSE:
            refused = Validated(None, RefusalReason.GATE)
            query_id = await self._store.save(
                record(
                    outcome=Outcome.NO_ANSWER,
                    band=band,
                    refusal_reason=RefusalReason.GATE,
                    answer=None,
                    top_score=top,
                    nearest_document_ids=[c.document_id for c in nearest],
                )
            )
            payload = self._final_payload(query_id, Outcome.NO_ANSWER, band, refused, [], nearest)
            if ask.debug:
                payload["diagnostics"] = diagnostics(
                    retrieved, band, self._provider.model, None, elapsed_ms()
                )
            yield Event("final", payload)
            return

        prompt = build_prompt(
            ask.question,
            [Excerpt(c.title, c.page_number, c.text, c.language, c.is_seed) for c in context],
        )
        llm_fields = {"llm_provider": self._provider.name, "llm_model": self._provider.model}
        if self._provider.hosted and not prompt.all_seed:
            # Checked again inside the provider; this keeps the request out of the queue.
            await self._store.save(
                record(
                    outcome=Outcome.ERROR,
                    band=band,
                    refusal_reason=None,
                    answer=None,
                    top_score=top,
                    error_code=ErrorCode.HOSTED_LLM_NON_SEED_DATA.value,
                    **llm_fields,
                )
            )
            yield _error(ErrorCode.HOSTED_LLM_NON_SEED_DATA)
            return

        samples = await self._store.recent_perf(self._provider.model, self._ls.eta_sample_count)
        eta = expected_seconds(
            samples, prompt.chars, self._queue.ahead(), self._ls.eta_default_seconds
        )
        yield Event("eta", {"expected_seconds": eta})

        holdback = SentinelHoldback()
        raw: list[str] = []
        done: Done | None = None
        writing = False
        try:
            async with self._queue.slot():
                async for delta in self._provider.stream(prompt):
                    if isinstance(delta, Done):
                        done = delta
                        continue
                    raw.append(delta.text)
                    released = holdback.feed(delta.text)
                    if released:
                        if not writing:
                            writing = True
                            yield _stage("writing")
                        yield Event("token", {"text": released})
        except (LlmUnavailableError, HostedNonSeedDataError) as exc:
            code = (
                ErrorCode.HOSTED_LLM_NON_SEED_DATA
                if isinstance(exc, HostedNonSeedDataError)
                else ErrorCode.LLM_UNAVAILABLE
            )
            logger.warning("ask: generation failed (%s)", code.value, exc_info=True)
            await self._store.save(
                record(
                    outcome=Outcome.ERROR,
                    band=band,
                    refusal_reason=None,
                    answer=None,
                    top_score=top,
                    error_code=code.value,
                    **llm_fields,
                )
            )
            yield _error(code)
            return

        text = "".join(raw)
        refused_by_provider = done is not None and done.refused
        validated = (
            Validated(None, RefusalReason.SENTINEL)
            if refused_by_provider
            else validate(text, prompt.excerpt_count)
        )
        held = holdback.finish()
        if validated.answer is not None and held:
            if not writing:
                yield _stage("writing")
            yield Event("token", {"text": held})

        if validated.answer is None:
            outcome = Outcome.NO_ANSWER
        elif band is Band.LOW_CONFIDENCE:
            outcome = Outcome.LOW_CONFIDENCE
        else:
            outcome = Outcome.ANSWERED
        perf = (
            PerfRecord(
                prompt_chars=prompt.chars,
                prompt_tokens=done.prompt_tokens,
                prompt_ms=done.prompt_ms,
                output_tokens=done.completion_tokens,
                output_ms=done.output_ms,
            )
            if done is not None
            else None
        )
        query_id = await self._store.save(
            record(
                outcome=outcome,
                band=band,
                refusal_reason=validated.refusal,
                answer=validated.answer,
                top_score=top,
                nearest_document_ids=(
                    [c.document_id for c in nearest] if validated.answer is None else []
                ),
                prompt_tokens=done.prompt_tokens if done else None,
                completion_tokens=done.completion_tokens if done else None,
                citations=[
                    CitationRecord(rank, context[n - 1].chunk_id, context[n - 1].score)
                    for rank, n in enumerate(validated.cited, start=1)
                ],
                perf=perf,
                **llm_fields,
            )
        )
        shown_nearest = nearest if validated.answer is None else []
        payload = self._final_payload(query_id, outcome, band, validated, context, shown_nearest)
        if ask.debug:
            payload["diagnostics"] = diagnostics(
                retrieved, band, self._provider.model, done, elapsed_ms()
            )
        yield Event("final", payload)
