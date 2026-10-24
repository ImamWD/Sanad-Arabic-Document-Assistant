"""GET /api/health: reachability of the services the API depends on (up or down, nothing more)."""

import asyncio
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from sanad.core.config import get_settings
from sanad.core.health import ProbeStatus, probe_db, probe_ml

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    db: ProbeStatus
    ml: ProbeStatus


@router.get(
    "/health",
    response_model=Health,
    responses={503: {"model": Health, "description": "A dependency is down"}},
)
async def health(request: Request, response: Response) -> Health:
    settings = get_settings()
    timeout = settings.health_timeout_seconds
    db_status, ml_status = await asyncio.gather(
        probe_db(request.app.state.db_engine, timeout),
        probe_ml(request.app.state.http_client, settings.ml_base_url, timeout),
    )
    healthy = db_status == ProbeStatus.OK and ml_status == ProbeStatus.OK
    if not healthy:
        response.status_code = 503
    return Health(status="ok" if healthy else "degraded", db=db_status, ml=ml_status)
