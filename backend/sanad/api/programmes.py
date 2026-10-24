"""GET /api/programmes: filter options with bilingual names, for any signed-in user."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from sanad.core.db import DbSession
from sanad.core.models import Programme
from sanad.core.security import CurrentUser

router = APIRouter(tags=["programmes"])


class ProgrammeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name_ar: str
    name_en: str


@router.get("/programmes", response_model=list[ProgrammeOut])
async def list_programmes(_: CurrentUser, db: DbSession) -> list[ProgrammeOut]:
    programmes = await db.scalars(
        select(Programme).where(Programme.is_active.is_(True)).order_by(Programme.code)
    )
    return [ProgrammeOut.model_validate(p) for p in programmes]
