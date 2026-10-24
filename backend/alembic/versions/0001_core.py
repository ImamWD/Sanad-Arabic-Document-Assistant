"""core: users, sessions, programmes, audit_events, and the shared enum types

Revision ID: 0001_core
Revises:

B3's 0002_documents and R1's 0003_queries chain onto this id. Enum values are written out
here, not imported from the models, so this revision never changes after the fact.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_core"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUMS = {
    "user_role": ("viewer", "editor", "admin"),
    "ui_lang": ("ar", "en"),
    # The client's six categories (Q5). No "other": NULL means uncategorised. Used by B3.
    "doc_category": (
        "annual_report",
        "donor_agreement",
        "programme_evaluation",
        "field_survey",
        "budget",
        "board_minutes",
    ),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def _timestamp(name: str, *, nullable: bool = False, default: bool = True) -> sa.Column[object]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.func.now() if default else None,
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind)

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", _enum("user_role"), nullable=False, server_default="viewer"),
        sa.Column("preferred_language", _enum("ui_lang"), nullable=False, server_default="en"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.false()),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        _timestamp("last_login_at", nullable=True, default=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        # The guest only ever reads; an admin can't promote it.
        sa.CheckConstraint("NOT is_guest OR role = 'viewer'", name="ck_users_guest_is_viewer"),
    )
    # At most one guest account.
    op.create_index(
        "uq_users_single_guest",
        "users",
        ["is_guest"],
        unique=True,
        postgresql_where=sa.text("is_guest"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Text(), primary_key=True),  # sha256 of the cookie token
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _timestamp("created_at"),
        _timestamp("expires_at", default=False),
        _timestamp("last_seen_at"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "programmes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name_ar", sa.Text(), nullable=False),
        sa.Column("name_en", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code", name="uq_programmes_code"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "meta", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        _timestamp("created_at"),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("programmes")
    op.drop_table("sessions")
    op.drop_table("users")
    bind = op.get_bind()
    for name in reversed(ENUMS):
        postgresql.ENUM(name=name).drop(bind)
    op.execute("DROP EXTENSION IF EXISTS citext")
