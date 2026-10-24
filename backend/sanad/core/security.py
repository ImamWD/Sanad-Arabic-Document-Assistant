"""Authentication and authorisation: the contract every router codes against.

    from sanad.core.security import CurrentUser, Role, User, require_role

    @router.get("/things")
    async def things(user: CurrentUser) -> ...:                      # any signed-in user
        ...  # user.role, user.is_guest

    @router.post("/things")
    async def add(user: Annotated[User, Depends(require_role(Role.EDITOR, Role.ADMIN))]) -> ...:
        ...

Sessions are opaque: the cookie holds a random token and the `sessions` table holds only its
sha256. A session ends on logout, after `SESSION_IDLE_MINUTES` without a request, after
`SESSION_ABSOLUTE_HOURS` in any case, and when an admin deactivates the user.

CSRF (SYSTEM_DESIGN §9): `csrf_guard` runs on every route. A state-changing request must carry
`X-Sanad: 1` and a JSON or multipart body, which a cross-site form can't send.
"""

import hashlib
import secrets
import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import Depends, Request, Response
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sanad.core.config import Settings, get_settings
from sanad.core.db import DbSession
from sanad.core.errors import ApiError, ErrorCode
from sanad.core.models import Role, User, UserSession

__all__ = [
    "CSRF_HEADER",
    "SESSION_COOKIE",
    "CurrentUser",
    "Role",
    "User",
    "clear_session_cookie",
    "create_session",
    "csrf_guard",
    "end_session",
    "get_current_user",
    "require_role",
    "revoke_sessions",
    "set_session_cookie",
]

SESSION_COOKIE = "sanad_session"
COOKIE_PATH = "/api"
CSRF_HEADER = "X-Sanad"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_CSRF_MEDIA_TYPES = frozenset({"application/json", "multipart/form-data"})
# last_seen_at is written at most this often, not on every request.
_LAST_SEEN_RESOLUTION = timedelta(minutes=1)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _idle_cutoff(settings: Settings, now: datetime) -> datetime:
    return now - timedelta(minutes=settings.session_idle_minutes)


async def create_session(db: AsyncSession, user: User) -> str:
    """Add a session for `user` (written on the caller's commit) and return the cookie token.
    Expired sessions of every user are swept at the same time."""
    settings = get_settings()
    now = datetime.now(UTC)
    await db.execute(
        delete(UserSession).where(
            or_(
                UserSession.expires_at <= now,
                UserSession.last_seen_at <= _idle_cutoff(settings, now),
            )
        )
    )
    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            id=_hash_token(token),
            user_id=user.id,
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(hours=settings.session_absolute_hours),
        )
    )
    return token


async def end_session(db: AsyncSession, token: str) -> uuid.UUID | None:
    """Delete the session behind `token`; return its user's id, if it existed."""
    result = await db.execute(
        delete(UserSession)
        .where(UserSession.id == _hash_token(token))
        .returning(UserSession.user_id)
    )
    return result.scalar_one_or_none()


async def revoke_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Sign the user out everywhere (on the caller's commit)."""
    await db.execute(delete(UserSession).where(UserSession.user_id == user_id))


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_absolute_hours * 3600,
        path=COOKIE_PATH,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        SESSION_COOKIE,
        path=COOKIE_PATH,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _unauthenticated() -> ApiError:
    return ApiError(401, ErrorCode.UNAUTHENTICATED)


async def get_current_user(request: Request, db: DbSession) -> User:
    """The signed-in user, or 401 UNAUTHENTICATED."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise _unauthenticated()
    settings = get_settings()
    now = datetime.now(UTC)
    row = (
        await db.execute(
            select(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .where(UserSession.id == _hash_token(token))
        )
    ).one_or_none()
    if row is None:
        raise _unauthenticated()
    session, user = row
    if session.expires_at <= now or session.last_seen_at <= _idle_cutoff(settings, now):
        await db.delete(session)
        await db.commit()
        raise _unauthenticated()
    # Deactivation already deletes the sessions; this is the second lock on the same door.
    if not user.is_active or (user.is_guest and settings.guest_mode == "off"):
        raise _unauthenticated()
    if now - session.last_seen_at >= _LAST_SEEN_RESOLUTION:
        session.last_seen_at = now
        await db.commit()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: Role) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Dependency factory: the signed-in user if their role is one of `roles`, else 403 FORBIDDEN.

    The guest is a viewer, so it passes only where `Role.VIEWER` is allowed.
    """
    allowed = frozenset(Role(r) for r in roles)

    async def dependency(user: CurrentUser) -> User:
        if user.role not in allowed or (user.is_guest and Role.VIEWER not in allowed):
            raise ApiError(403, ErrorCode.FORBIDDEN)
        return user

    return dependency


async def csrf_guard(request: Request) -> None:
    """Installed app-wide (see sanad.api.main), so every route gets it, including later ones."""
    if request.method in _SAFE_METHODS:
        return
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if request.headers.get(CSRF_HEADER) != "1" or media_type not in _CSRF_MEDIA_TYPES:
        raise ApiError(403, ErrorCode.CSRF_REJECTED)
