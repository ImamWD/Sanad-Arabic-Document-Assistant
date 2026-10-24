"""FastAPI application. Run with `uvicorn sanad.api.main:app`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx2
from fastapi import FastAPI

from sanad.api import health
from sanad.core.config import get_settings
from sanad.core.db import create_engine
from sanad.core.errors import install_error_handlers

API_PREFIX = "/api"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    app.state.db_engine = create_engine(settings)
    app.state.http_client = httpx2.AsyncClient()
    try:
        yield
    finally:
        await app.state.http_client.aclose()
        await app.state.db_engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sanad API",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=None,
        redoc_url=None,
    )
    install_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    return app


app = create_app()
