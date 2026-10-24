"""Revision 0001_core: its id (B3 and R1 chain onto it), the enum types later revisions use,
and a clean downgrade."""

import secrets
from collections.abc import Iterator

import pytest
import sqlalchemy
from alembic.script import ScriptDirectory
from sqlalchemy import text

from alembic import command
from sanad.core.config import Settings
from sanad.core.models import DocCategory, Language, Role
from tests.api.conftest import alembic_config


@pytest.fixture
def scratch_db(settings: Settings) -> Iterator[sqlalchemy.Engine]:
    """An empty database next to the test database, for migrating up and down."""
    name = f"{settings.postgres_db}_mig_{secrets.token_hex(3)}"
    server = sqlalchemy.create_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    engine = sqlalchemy.create_engine(settings.database_url.set(database=name))
    try:
        yield engine
    finally:
        engine.dispose()
        with server.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        server.dispose()


def _enum_values(conn: sqlalchemy.Connection, name: str) -> list[str]:
    return list(
        conn.scalars(
            text(
                "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid"
                " WHERE t.typname = :name ORDER BY e.enumsortorder"
            ),
            {"name": name},
        )
    )


def test_first_revision_is_0001_core(engine: sqlalchemy.Engine) -> None:
    with engine.connect() as conn:
        script = ScriptDirectory.from_config(alembic_config(conn))
    assert script.get_base() == "0001_core"
    assert script.get_revision("0001_core").down_revision is None


def test_enum_types_match_the_models(engine: sqlalchemy.Engine) -> None:
    with engine.connect() as conn:
        assert _enum_values(conn, "user_role") == [r.value for r in Role]
        assert _enum_values(conn, "ui_lang") == [lang.value for lang in Language]
        assert _enum_values(conn, "doc_category") == [
            "annual_report",
            "donor_agreement",
            "programme_evaluation",
            "field_survey",
            "budget",
            "board_minutes",
        ]
        assert _enum_values(conn, "doc_category") == [c.value for c in DocCategory]


def test_upgrade_downgrade_upgrade(scratch_db: sqlalchemy.Engine) -> None:
    tables = text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1")
    with scratch_db.begin() as conn:
        command.upgrade(alembic_config(conn), "0001_core")
    with scratch_db.connect() as conn:
        assert list(conn.scalars(tables)) == [
            "alembic_version",
            "audit_events",
            "programmes",
            "sessions",
            "users",
        ]

    with scratch_db.begin() as conn:
        command.downgrade(alembic_config(conn), "base")
    with scratch_db.connect() as conn:
        assert list(conn.scalars(tables)) == ["alembic_version"]
        assert _enum_values(conn, "doc_category") == []

    with scratch_db.begin() as conn:
        command.upgrade(alembic_config(conn), "0001_core")
