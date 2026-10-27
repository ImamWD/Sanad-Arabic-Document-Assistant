"""One-shot initialisation: `python -m sanad.init`.

The compose `init` service runs `alembic upgrade head` and then this, on every
`docker compose up`, before api and worker start. So every step must be idempotent.

Later tasks append their own steps to STEPS (append-only). A step receives a sync Session,
already inside its own transaction (committed when the step returns), and the Settings.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from sanad.core import passwords
from sanad.core.config import (
    InsecureDefaultsError,
    Settings,
    check_public_defaults,
    get_settings,
)
from sanad.core.db import create_sync_engine
from sanad.core.models import Language, Programme, Role, User
from sanad.documents.seed import register_seed_documents

logger = logging.getLogger(__name__)

Step = Callable[[Session, Settings], None]


def seed_programmes(db: Session, settings: Settings) -> None:
    """Insert or update the programmes listed in seed/manifest.json (matched by code)."""
    manifest = json.loads((settings.seed_dir / "manifest.json").read_text(encoding="utf-8"))
    rows = [
        {"code": p["code"], "name_ar": p["name_ar"], "name_en": p["name_en"]}
        for p in manifest["programmes"]
    ]
    stmt = insert(Programme).values(rows)
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=[Programme.code],
            set_={"name_ar": stmt.excluded.name_ar, "name_en": stmt.excluded.name_en},
        )
    )


@dataclass(frozen=True)
class DemoAccount:
    email: str
    name: str
    role: Role
    password: SecretStr | None  # None: no password login (the guest)
    is_guest: bool = False


def demo_accounts(settings: Settings) -> list[DemoAccount]:
    return [
        DemoAccount("admin@sanad.example", "Demo Admin", Role.ADMIN, settings.demo_admin_password),
        DemoAccount(
            "editor@sanad.example", "Demo Editor", Role.EDITOR, settings.demo_editor_password
        ),
        DemoAccount(
            "viewer@sanad.example", "Demo Viewer", Role.VIEWER, settings.demo_viewer_password
        ),
        DemoAccount("guest@sanad.example", "Guest", Role.VIEWER, None, is_guest=True),
    ]


def seed_accounts(db: Session, settings: Settings) -> None:
    """Create the demo accounts that don't exist yet. Existing accounts are left alone, so a
    password or role changed since then survives a restart."""
    for account in demo_accounts(settings):
        if db.scalar(select(User.id).where(User.email == account.email)) is not None:
            continue
        password_hash = (
            passwords.hash_password(account.password.get_secret_value())
            if account.password is not None
            else passwords.UNUSABLE_PASSWORD_HASH
        )
        db.add(
            User(
                name=account.name,
                email=account.email,
                password_hash=password_hash,
                role=account.role,
                preferred_language=Language.EN,
                is_guest=account.is_guest,
            )
        )
        logger.info("created demo account %s", account.email)


STEPS: list[tuple[str, Step]] = [
    ("programmes", seed_programmes),
    ("accounts", seed_accounts),
    ("seed documents", register_seed_documents),  # B3: needs the programmes and an admin
]


def run(settings: Settings) -> None:
    engine = create_sync_engine(settings)
    try:
        for name, step in STEPS:
            with Session(engine) as db, db.begin():
                step(db, settings)
            logger.info("init step %s done", name)
    finally:
        engine.dispose()


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    try:
        # Before any step: a production deploy must not create demo accounts with public
        # passwords.
        check_public_defaults(settings, logger)
    except InsecureDefaultsError as err:
        logger.critical("%s", err)
        raise SystemExit(2) from None
    run(settings)


if __name__ == "__main__":
    main()
