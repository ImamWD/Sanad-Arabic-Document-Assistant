"""/api/admin/users: list, create and edit accounts (admin only). Accounts are never deleted;
an admin deactivates them, which also signs them out everywhere."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from sanad.core import audit, passwords
from sanad.core.config import get_settings
from sanad.core.db import DbSession
from sanad.core.errors import ApiError, ErrorCode
from sanad.core.models import Language
from sanad.core.security import Role, User, require_role, revoke_sessions

router = APIRouter(prefix="/admin/users", tags=["admin"])

Admin = Annotated[User, Depends(require_role(Role.ADMIN))]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]


class AdminUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: Role
    preferred_language: Language
    is_active: bool
    is_guest: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    email: Email
    password: str = Field(max_length=1024)
    role: Role
    preferred_language: Language


class UserUpdate(BaseModel):
    """Only the fields present are changed."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    role: Role | None = None
    is_active: bool | None = None
    preferred_language: Language | None = None


@router.get("", response_model=list[AdminUser])
async def list_users(_: Admin, db: DbSession) -> list[AdminUser]:
    users = await db.scalars(select(User).order_by(User.created_at, User.email))
    return [AdminUser.model_validate(u) for u in users]


@router.post("", response_model=AdminUser, status_code=201)
async def create_user(body: UserCreate, admin: Admin, db: DbSession) -> AdminUser:
    min_length = get_settings().password_min_length
    if len(body.password) < min_length:
        raise ApiError(422, ErrorCode.PASSWORD_TOO_SHORT, min_length=min_length)
    if await db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise ApiError(409, ErrorCode.EMAIL_TAKEN)
    user = User(
        name=body.name,
        email=body.email,
        password_hash=await run_in_threadpool(passwords.hash_password, body.password),
        role=body.role,
        preferred_language=body.preferred_language,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:  # a concurrent create with the same email
        raise ApiError(409, ErrorCode.EMAIL_TAKEN) from exc
    audit.record(
        db, "user.create", actor_id=admin.id, target_type="user", target_id=user.id, role=user.role
    )
    await db.commit()
    await db.refresh(user)
    return AdminUser.model_validate(user)


@router.patch("/{user_id}", response_model=AdminUser)
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, admin: Admin, db: DbSession
) -> AdminUser:
    user = await db.get(User, user_id)
    if user is None:
        raise ApiError(404, ErrorCode.NOT_FOUND)
    if user.is_guest and body.role not in (None, Role.VIEWER):
        raise ApiError(409, ErrorCode.GUEST_ROLE_FIXED)
    # An admin can't lock themselves out, which also guarantees one active admin remains.
    if user.id == admin.id and (body.role not in (None, Role.ADMIN) or body.is_active is False):
        raise ApiError(409, ErrorCode.CANNOT_CHANGE_OWN_ACCESS)

    changes: dict[str, Any] = {}
    for field in ("name", "role", "is_active", "preferred_language"):
        new = getattr(body, field)
        old = getattr(user, field)
        if new is not None and new != old:
            changes[field] = [old, new]
            setattr(user, field, new)
    if changes.get("is_active") == [True, False]:
        await revoke_sessions(db, user.id)
    if changes:
        audit.record(
            db, "user.update", actor_id=admin.id, target_type="user", target_id=user.id, **changes
        )
        await db.commit()
        await db.refresh(user)
    return AdminUser.model_validate(user)
