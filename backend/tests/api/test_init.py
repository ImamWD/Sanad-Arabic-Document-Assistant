"""`python -m sanad.init`: idempotent seeding of programmes and demo accounts, and the schema
rules that protect the guest account."""

import pytest
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from sanad import init
from sanad.core import passwords
from sanad.core.config import Settings
from tests.api.conftest import demo_password


def _users(engine: sqlalchemy.Engine) -> dict[str, sqlalchemy.Row[tuple[str, str, bool, str]]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT email, role::text, is_guest, password_hash FROM users")
        ).all()
    return {row.email: row for row in rows}


def test_demo_accounts(seeded: None, engine: sqlalchemy.Engine, settings: Settings) -> None:
    users = _users(engine)

    assert {email: (u.role, u.is_guest) for email, u in users.items()} == {
        "admin@sanad.example": ("admin", False),
        "editor@sanad.example": ("editor", False),
        "viewer@sanad.example": ("viewer", False),
        "guest@sanad.example": ("viewer", True),
    }
    for who in ("admin", "editor", "viewer"):
        stored = users[f"{who}@sanad.example"].password_hash
        assert stored.startswith("$argon2id$")
        assert passwords.verify_password(stored, demo_password(settings, who))
    guest_hash = users["guest@sanad.example"].password_hash
    assert guest_hash == passwords.UNUSABLE_PASSWORD_HASH
    assert not passwords.verify_password(guest_hash, "")


def test_init_is_idempotent_and_keeps_changed_accounts(
    seeded: None, engine: sqlalchemy.Engine, settings: Settings
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE users SET role = 'editor', password_hash = 'changed'"
                " WHERE email = 'viewer@sanad.example'"
            )
        )
        conn.execute(text("UPDATE programmes SET name_en = 'Old name' WHERE code = 'YEP'"))

    init.run(settings)
    init.run(settings)

    users = _users(engine)
    assert len(users) == 4
    assert (users["viewer@sanad.example"].role, users["viewer@sanad.example"].password_hash) == (
        "editor",
        "changed",
    )
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM programmes")) == 6
        # The manifest is the source of truth for programme names.
        assert conn.scalar(text("SELECT name_en FROM programmes WHERE code = 'YEP'")) == (
            "Youth Employment Empowerment Programme"
        )


def test_steps_are_named_and_ordered() -> None:
    assert [name for name, _ in init.STEPS][:2] == ["programmes", "accounts"]


@pytest.mark.parametrize(
    "sql",
    [
        # A second guest account.
        "INSERT INTO users (name, email, password_hash, is_guest)"
        " VALUES ('Guest 2', 'guest2@sanad.example', '!', true)",
        # A guest that is anything but a viewer.
        "UPDATE users SET role = 'admin' WHERE is_guest",
        # Two accounts whose emails differ only in case.
        "INSERT INTO users (name, email, password_hash)"
        " VALUES ('Shadow', 'ADMIN@sanad.example', '!')",
    ],
    ids=["second-guest", "guest-admin", "email-case"],
)
def test_schema_protects_accounts(seeded: None, engine: sqlalchemy.Engine, sql: str) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text(sql))
