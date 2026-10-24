"""Alembic environment. Online migrations only, against the database in sanad.core.config.

The URL is built from the POSTGRES_* settings and passed to the engine as a URL object, never
through alembic.ini, so a password with % or other special characters needs no escaping.
A caller may instead pass an open connection in `config.attributes["connection"]`.
"""

from logging.config import fileConfig

from sqlalchemy import Connection

from alembic import context
from sanad.core.config import get_settings
from sanad.core.db import create_sync_engine
from sanad.core.models import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _migrate(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _migrate(connection)
        return
    engine = create_sync_engine(get_settings())
    try:
        with engine.connect() as conn:
            _migrate(conn)
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise SystemExit("offline (--sql) migrations are not supported; run against the database")
run_migrations_online()
