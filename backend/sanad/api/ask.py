"""POST /api/ask (JSON) and POST /api/ask/stream (SSE): the same pipeline, two transports.

Every signed-in user may ask, the guest included; what they can retrieve is decided by
`retrievable_chunks(user)` inside the retriever. Event order and refusal rules: see
sanad.retrieval.pipeline.

The stream sets `X-Accel-Buffering: no` (deploy/nginx.conf relies on it) and sends `: ping`
whenever no event was due for SSE_PING_SECONDS, so a long prompt-processing wait on CPU never
looks like a dead connection. Errors after the stream has started arrive as an `error` event.
"""

import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, StringConstraints

from sanad.api.queries import session_id_of
from sanad.core.config import get_settings
from sanad.core.db import DbSession
from sanad.core.errors import ApiError, ErrorCode
from sanad.core.models import DocCategory
from sanad.core.security import CurrentUser, Role, User
from sanad.llm.providers import build_provider
from sanad.llm.queue import GenerationQueue
from sanad.llm.settings import get_llm_settings
from sanad.retrieval.ml import AskMlClient
from sanad.retrieval.pipeline import AskInput, AskPipeline, Event
from sanad.retrieval.schemas import AskResult
from sanad.retrieval.search import SqlRetriever
from sanad.retrieval.settings import get_retrieval_settings
from sanad.retrieval.store import SqlQueryStore
from sanad.retrieval.types import Filters

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Runs inside the app's own lifespan, so the db engine and http client already exist."""
    llm = get_llm_settings()
    app.state.llm_provider = build_provider(llm)
    app.state.generation_queue = GenerationQueue(llm.llm_max_concurrency)
    try:
        yield
    finally:
        await app.state.llm_provider.aclose()


router = APIRouter(tags=["ask"], lifespan=lifespan)

QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AskFilters(BaseModel):
    programme_id: uuid.UUID | None = None
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    category: DocCategory | None = None


class AskRequest(BaseModel):
    question: QuestionText
    filters: AskFilters | None = None
    # POST /ask only: retrieval diagnostics for editors and admins when ASK_DEBUG_ENABLED is on.
    # Silently ignored for anyone else and on the stream.
    debug: bool = False


def get_pipeline(request: Request) -> AskPipeline:
    app = request.app
    retrieval = get_retrieval_settings()
    ml = AskMlClient(
        app.state.http_client, get_settings().ml_base_url, retrieval.ask_ml_timeout_seconds
    )
    return AskPipeline(
        retriever=SqlRetriever(app.state.db_engine, ml, retrieval),
        store=SqlQueryStore(app.state.db_engine),
        provider=app.state.llm_provider,
        queue=app.state.generation_queue,
        retrieval=retrieval,
        llm=get_llm_settings(),
    )


Pipeline = Annotated[AskPipeline, Depends(get_pipeline)]


async def _ask_input(
    body: AskRequest, request: Request, user: CurrentUser, db: DbSession, *, debug: bool = False
) -> AskInput:
    """Validate the request and release the request's db connection: the pipeline opens its own
    sessions, and an answer can take minutes on CPU."""
    await db.close()
    if len(body.question) > get_retrieval_settings().question_max_chars:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, fields=["body.question"])
    f = body.filters or AskFilters()
    filters = Filters(
        programme_id=f.programme_id,
        year_from=f.year_from,
        year_to=f.year_to,
        category=f.category.value if f.category else None,
    )
    return AskInput(
        user=user,
        session_id=session_id_of(request),
        question=body.question,
        filters=filters,
        debug=debug and may_debug(user),
    )


def may_debug(user: User) -> bool:
    return (
        get_retrieval_settings().ask_debug_enabled
        and not user.is_guest
        and user.role in (Role.EDITOR, Role.ADMIN)
    )


@router.post(
    "/ask",
    response_model=AskResult,
    # `diagnostics` is left out entirely, not sent as null, unless it was asked for and allowed.
    response_model_exclude_unset=True,
    responses={503: {"description": "SEARCH_UNAVAILABLE, LLM_UNAVAILABLE, ..."}},
)
async def ask(
    body: AskRequest, request: Request, user: CurrentUser, db: DbSession, pipeline: Pipeline
) -> Any:
    ask_input = await _ask_input(body, request, user, db, debug=body.debug)
    async for event in pipeline.run(ask_input):
        if event.name == "final":
            return event.data
        if event.name == "error":
            raise ApiError(event.status, ErrorCode(event.data["error"]["code"]))
    raise ApiError(500, ErrorCode.INTERNAL_ERROR)  # pragma: no cover - the pipeline always ends


def format_event(event: Event) -> str:
    return f"event: {event.name}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


async def sse(events: AsyncIterator[Event], ping_seconds: float) -> AsyncIterator[str]:
    """Run the pipeline in its own task and relay its events, with pings in between. Leaving
    early (the client went away) cancels the pipeline, which frees its generation slot."""
    queue: asyncio.Queue[Event | None] = asyncio.Queue()

    async def produce() -> None:
        try:
            async for event in events:
                await queue.put(event)
        except Exception:
            logger.exception("ask stream failed")
            await queue.put(Event("error", {"error": {"code": "INTERNAL_ERROR", "params": {}}}))
        finally:
            await queue.put(None)

    task = asyncio.create_task(produce())
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=ping_seconds)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            if event is None:
                break
            yield format_event(event)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@router.post(
    "/ask/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "SSE events"}},
)
async def ask_stream(
    body: AskRequest, request: Request, user: CurrentUser, db: DbSession, pipeline: Pipeline
) -> StreamingResponse:
    events = pipeline.run(await _ask_input(body, request, user, db))
    return StreamingResponse(
        sse(events, get_llm_settings().sse_ping_seconds),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
