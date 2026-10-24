"""Reachability probes for the services the API depends on."""

import asyncio
import logging
from collections.abc import Awaitable
from enum import StrEnum

import httpx2
from sqlalchemy.ext.asyncio import AsyncEngine

from sanad.core import db

logger = logging.getLogger(__name__)


class ProbeStatus(StrEnum):
    OK = "ok"
    DOWN = "down"


async def _probe(name: str, check: Awaitable[None], timeout: float) -> ProbeStatus:
    try:
        await asyncio.wait_for(check, timeout=timeout)
    except Exception:
        # The reason goes to the server log only; the response says up or down.
        logger.warning("health probe %s failed", name, exc_info=True)
        return ProbeStatus.DOWN
    return ProbeStatus.OK


async def _check_ml(client: httpx2.AsyncClient, ml_base_url: str) -> None:
    response = await client.get(f"{ml_base_url}/health")
    response.raise_for_status()
    if response.json().get("status") != ProbeStatus.OK:
        raise RuntimeError("ml reported not ok")


async def probe_db(engine: AsyncEngine, timeout: float) -> ProbeStatus:
    return await _probe("db", db.ping(engine), timeout)


async def probe_ml(client: httpx2.AsyncClient, ml_base_url: str, timeout: float) -> ProbeStatus:
    return await _probe("ml", _check_ml(client, ml_base_url), timeout)
