"""GET and PATCH /api/me: the signed-in user's profile and interface language."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from sanad.core.db import DbSession
from sanad.core.errors import ApiError, ErrorCode
from sanad.core.models import Language
from sanad.core.security import CurrentUser, Role

router = APIRouter(tags=["me"])


class Me(BaseModel):
    """Also the body of a successful login (POST /auth/login and /auth/guest)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: Role
    preferred_language: Language
    is_guest: bool


class MeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_language: Language


@router.get("/me", response_model=Me)
async def get_me(user: CurrentUser) -> Me:
    return Me.model_validate(user)


@router.patch("/me", response_model=Me)
async def update_me(body: MeUpdate, user: CurrentUser, db: DbSession) -> Me:
    # The guest account is shared by everyone who clicks "Continue as guest".
    if user.is_guest:
        raise ApiError(403, ErrorCode.FORBIDDEN)
    user.preferred_language = body.preferred_language
    await db.commit()
    return Me.model_validate(user)
