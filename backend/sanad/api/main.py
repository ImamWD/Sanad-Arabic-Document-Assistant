"""FastAPI application. Run with `uvicorn sanad.api.main:app`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx2
from fastapi import Depends, FastAPI

from sanad.api import admin_users, ask, auth, documents, health, me, programmes, queries
from sanad.core.config import InsecureDefaultsError, check_public_defaults, get_settings
from sanad.core.db import create_engine
from sanad.core.errors import install_error_handlers
from sanad.core.ratelimit import LoginRateLimiter
from sanad.core.security import csrf_guard

API_PREFIX = "/api"

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    try:
        # In production this refuses to serve with public defaults (startup fails, the
        # container exits); in demo it logs which ones are in use.
        check_public_defaults(settings, logger)
    except InsecureDefaultsError as err:
        logger.critical("%s", err)
        raise
    app.state.db_engine = create_engine(settings)
    app.state.http_client = httpx2.AsyncClient()
    try:
        yield
    finally:
        await app.state.http_client.aclose()
        await app.state.db_engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Sanad API",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=None,
        redoc_url=None,
        # App-wide, so every router gets the CSRF check, including ones added later. As a
        # dependency (not middleware) it runs only for matched routes: 404 and 405 stay as they are.
        dependencies=[Depends(csrf_guard)],
    )
    install_error_handlers(app)
    app.state.login_limiter = LoginRateLimiter(
        window_seconds=settings.login_window_seconds,
        max_failures_per_email=settings.login_max_failures_per_email,
        max_failures_per_ip=settings.login_max_failures_per_ip,
    )
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(me.router, prefix=API_PREFIX)
    app.include_router(admin_users.router, prefix=API_PREFIX)
    app.include_router(programmes.router, prefix=API_PREFIX)
    app.include_router(documents.router, prefix=API_PREFIX)
    app.include_router(ask.router, prefix=API_PREFIX)
    app.include_router(queries.router, prefix=API_PREFIX)
    return app


app = create_app()
