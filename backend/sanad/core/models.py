"""ORM models for the core tables (Alembic revision 0001_core).

Later tasks add their own models on the same `Base`. The Postgres enum types are created by
the migrations, never by the ORM (`create_type=False`).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, Text, func, text
from sqlalchemy.dialects.postgresql import CITEXT, ENUM, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Role(StrEnum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


class Language(StrEnum):
    AR = "ar"
    EN = "en"


class DocCategory(StrEnum):
    """The client's six categories (Q5). There is no "other": NULL means uncategorised."""

    ANNUAL_REPORT = "annual_report"
    DONOR_AGREEMENT = "donor_agreement"
    PROGRAMME_EVALUATION = "programme_evaluation"
    FIELD_SURVEY = "field_survey"
    BUDGET = "budget"
    BOARD_MINUTES = "board_minutes"


def _pg_enum(enum: type[StrEnum], name: str) -> ENUM:
    return ENUM(
        enum,
        name=name,
        values_callable=lambda members: [m.value for m in members],
        create_type=False,
        validate_strings=True,
    )


ROLE_ENUM = _pg_enum(Role, "user_role")
LANGUAGE_ENUM = _pg_enum(Language, "ui_lang")
# For B3's documents.category column; the type itself is created by 0001_core.
DOC_CATEGORY_ENUM = _pg_enum(DocCategory, "doc_category")

_NOW = text("now()")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[Role] = mapped_column(ROLE_ENUM, server_default=Role.VIEWER.value)
    preferred_language: Mapped[Language] = mapped_column(
        LANGUAGE_ENUM, server_default=Language.EN.value
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    # The guest is always a viewer (check constraint) and sees seed documents only.
    is_guest: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=_NOW, onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    """A signed-in browser. `id` is the sha256 of the cookie token; the token itself is never
    stored. Deleting the row signs the browser out."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class Programme(Base):
    __tablename__ = "programmes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    code: Mapped[str] = mapped_column(Text, unique=True)
    name_ar: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class AuditEvent(Base):
    """Admin-visible trail: logins, user changes, and later uploads and archives."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(Text)
    target_type: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=_NOW, index=True
    )
