"""GET /api/queries and /api/queries/{id}: the signed-in user's own questions (history panel).

The guest is one shared account, so for the guest both routes see only the current session's
questions. Someone else's question, or another guest session's, is 404 NOT_FOUND.
"""

import hashlib
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from sanad.core.db import DbSession
from sanad.core.errors import ApiError, ErrorCode
from sanad.core.security import SESSION_COOKIE, CurrentUser
from sanad.retrieval.schemas import StoredAnswer
from sanad.retrieval.settings import get_retrieval_settings
from sanad.retrieval.store import history, stored_answer
from sanad.retrieval.types import Outcome

router = APIRouter(tags=["queries"])


def session_id_of(request: Request) -> str | None:
    """The current session's id as stored in `sessions.id`: the sha256 of the cookie token.
    Only called after `get_current_user` has accepted that cookie."""
    token = request.cookies.get(SESSION_COOKIE)
    return hashlib.sha256(token.encode()).hexdigest() if token else None


class QuerySummary(BaseModel):
    id: uuid.UUID
    question: str
    outcome: Outcome
    created_at: datetime


@router.get("/queries", response_model=list[QuerySummary])
async def list_queries(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[QuerySummary]:
    rows = await history(db, user, session_id_of(request), limit)
    return [
        QuerySummary(id=q.id, question=q.question, outcome=q.outcome, created_at=q.created_at)
        for q in rows
    ]


@router.get(
    "/queries/{query_id}",
    response_model=StoredAnswer,
    responses={404: {"description": "Not one of the caller's questions"}},
)
async def get_query(
    query_id: uuid.UUID, request: Request, user: CurrentUser, db: DbSession
) -> StoredAnswer:
    found = await stored_answer(
        db, user, session_id_of(request), query_id, get_retrieval_settings().snippet_chars
    )
    if found is None:
        raise ApiError(404, ErrorCode.NOT_FOUND)
    return StoredAnswer.model_validate(found)
