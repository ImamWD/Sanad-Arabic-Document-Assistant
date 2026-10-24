"""POST /api/auth/login, /logout and /guest: cookie sessions (SYSTEM_DESIGN §7, §9)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from sanad.api.me import Me
from sanad.core import audit, passwords
from sanad.core.config import get_settings
from sanad.core.db import DbSession
from sanad.core.errors import ApiError, ErrorCode
from sanad.core.ratelimit import LoginRateLimiter
from sanad.core.security import (
    SESSION_COOKIE,
    User,
    clear_session_cookie,
    create_session,
    end_session,
    set_session_cookie,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


def _client_ip(request: Request) -> str:
    # nginx overwrites X-Real-IP with the peer address, and api is reachable only through nginx
    # (internal network), so the header can be trusted. Without it, use the socket peer.
    return request.headers.get("x-real-ip") or (
        request.client.host if request.client else "unknown"
    )


async def _start_session(request: Request, response: Response, db: DbSession, user: User) -> Me:
    # A login replaces whatever session this browser had.
    if old_token := request.cookies.get(SESSION_COOKIE):
        await end_session(db, old_token)
    token = await create_session(db, user)
    user.last_login_at = datetime.now(UTC)
    await db.commit()
    set_session_cookie(response, token)
    return Me.model_validate(user)


@router.post("/login", response_model=Me)
async def login(body: LoginRequest, request: Request, response: Response, db: DbSession) -> Me:
    limiter: LoginRateLimiter = request.app.state.login_limiter
    email = body.email.strip()
    ip = _client_ip(request)
    if (wait := limiter.retry_after(email, ip)) is not None:
        raise ApiError(429, ErrorCode.RATE_LIMITED, retry_after_seconds=wait)

    user = await db.scalar(select(User).where(User.email == email))
    if user is None or user.is_guest:
        await run_in_threadpool(passwords.burn_verify_time, body.password)
        verified = False
    else:
        verified = await run_in_threadpool(
            passwords.verify_password, user.password_hash, body.password
        )
    if user is None or not verified:
        limiter.record_failure(email, ip)
        audit.record(
            db,
            "auth.login_failed",
            actor_id=None,
            target_type="user" if user else None,
            target_id=user.id if user else None,
        )
        await db.commit()
        raise ApiError(401, ErrorCode.INVALID_CREDENTIALS)
    if not user.is_active:
        raise ApiError(403, ErrorCode.ACCOUNT_DISABLED)

    limiter.reset_email(email)
    if passwords.needs_rehash(user.password_hash):
        user.password_hash = await run_in_threadpool(passwords.hash_password, body.password)
    audit.record(db, "auth.login", actor_id=user.id)
    return await _start_session(request, response, db, user)


@router.post("/guest", response_model=Me)
async def guest_login(request: Request, response: Response, db: DbSession) -> Me:
    if get_settings().guest_mode == "off":
        raise ApiError(403, ErrorCode.GUEST_DISABLED)
    guest = await db.scalar(select(User).where(User.is_guest.is_(True)))
    if guest is None or not guest.is_active:
        raise ApiError(403, ErrorCode.GUEST_DISABLED)
    audit.record(db, "auth.guest_login", actor_id=guest.id)
    return await _start_session(request, response, db, guest)


@router.post("/logout", status_code=204, response_class=Response)
async def logout(request: Request, db: DbSession) -> Response:
    """Always succeeds; signing out without a session is not an error."""
    if token := request.cookies.get(SESSION_COOKIE):
        user_id = await end_session(db, token)
        if user_id is not None:
            audit.record(db, "auth.logout", actor_id=user_id)
        await db.commit()
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response
