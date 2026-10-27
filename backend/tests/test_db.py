"""The api and init engines never print bound values when a statement fails.

A failed statement's exception reaches the server log with exc_info (errors._unhandled_error).
SQLAlchemy formats bound values into it as `[parameters: ...]` unless the engine sets
hide_parameters, and those values can be a question with its answer, or a password hash.
"""

import asyncio
import traceback

import pytest
from sqlalchemy import text
from sqlalchemy.exc import StatementError

from sanad.core.config import get_settings
from sanad.core.db import create_engine, create_sync_engine

# Bound alongside a division by zero: Postgres reports the division, never this value, so
# anything of it in the formatted exception came from SQLAlchemy's parameter dump.
QUESTION_AND_ANSWER = "كم خُصّص لرواتب فريق المشروع؟ الجواب: 84,000"
FAILING = text("SELECT CAST(:qa AS text), 1 / CAST(:zero AS integer)")
PARAMS = {"qa": QUESTION_AND_ANSWER, "zero": 0}


def _assert_hidden(exc: StatementError) -> None:
    formatted = "".join(traceback.format_exception(exc))
    assert "division by zero" in formatted  # it is the error we provoked
    assert QUESTION_AND_ANSWER not in formatted
    assert "84,000" not in formatted
    assert "parameters:" not in formatted


def test_api_engine_hides_bound_values() -> None:
    async def provoke() -> StatementError:
        engine = create_engine(get_settings())
        try:
            async with engine.connect() as conn:
                with pytest.raises(StatementError) as excinfo:
                    await conn.execute(FAILING, PARAMS)
                return excinfo.value
        finally:
            await engine.dispose()

    _assert_hidden(asyncio.run(provoke()))


def test_sync_engine_hides_bound_values() -> None:
    engine = create_sync_engine(get_settings())
    try:
        with engine.connect() as conn, pytest.raises(StatementError) as excinfo:
            conn.execute(FAILING, PARAMS)
    finally:
        engine.dispose()
    _assert_hidden(excinfo.value)
