"""Every server error code must be translated in both UI locales (CLAUDE.md rule 6)."""

import json
from pathlib import Path

import pytest

from sanad.core.errors import ErrorCode

LOCALES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "locales"


@pytest.mark.parametrize("locale", ["ar", "en"])
def test_every_error_code_is_translated(locale: str) -> None:
    messages = json.loads((LOCALES / f"{locale}.json").read_text(encoding="utf-8"))
    errors = messages.get("errors", {})
    missing = [code.value for code in ErrorCode if not str(errors.get(code.value, "")).strip()]
    assert missing == [], f"{locale}.json lacks errors.* keys for {missing}"
