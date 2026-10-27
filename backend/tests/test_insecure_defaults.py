"""SANAD_ENV: production refuses public defaults at startup (api and init); demo warns."""

import logging
import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from sanad import init
from sanad.api.main import create_app
from sanad.core.config import (
    INSECURE_DEFAULTS,
    InsecureDefaultsError,
    Settings,
    check_public_defaults,
    get_settings,
)

ALL_FIVE = [
    "DEMO_ADMIN_PASSWORD",
    "DEMO_EDITOR_PASSWORD",
    "DEMO_VIEWER_PASSWORD",
    "POSTGRES_PASSWORD",
    "SESSION_COOKIE_SECURE",
]
DEFAULT_SECRETS = ["admin-demo-2026", "editor-demo-2026", "viewer-demo-2026"]

# Values that differ from every public default.
CHANGED = {
    "demo_admin_password": SecretStr("a-real-admin-secret"),
    "demo_editor_password": SecretStr("a-real-editor-secret"),
    "demo_viewer_password": SecretStr("a-real-viewer-secret"),
    "postgres_password": SecretStr("a-real-db-secret"),
    "session_cookie_secure": True,
}

log = logging.getLogger("test.insecure_defaults")


def _assert_no_values(text: str) -> None:
    for secret in DEFAULT_SECRETS:
        assert secret not in text
    # The default POSTGRES_PASSWORD is the bare word "sanad" ("SANAD_ENV" is fine).
    assert re.search(r"\bsanad\b", text, flags=re.IGNORECASE) is None


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Each test starts from the public defaults, whatever the container's environment says."""
    for name in [*ALL_FIVE, "SANAD_ENV"]:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_production_with_defaults_fails_and_names_all_five() -> None:
    with pytest.raises(InsecureDefaultsError) as caught:
        check_public_defaults(Settings(sanad_env="production"), log)

    assert caught.value.code == INSECURE_DEFAULTS
    assert caught.value.names == ALL_FIVE
    message = str(caught.value)
    assert message.startswith(f"{INSECURE_DEFAULTS}:")
    for name in ALL_FIVE:
        assert name in message
    _assert_no_values(message)


def test_production_with_everything_changed_passes(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        check_public_defaults(Settings(sanad_env="production", **CHANGED), log)  # type: ignore[arg-type]
    assert caplog.records == []


def test_demo_with_defaults_passes_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings()
    assert settings.sanad_env == "demo"

    with caplog.at_level(logging.WARNING):
        check_public_defaults(settings, log)

    assert [r.levelno for r in caplog.records] == [logging.WARNING]
    warning = caplog.records[0].getMessage()
    for name in ALL_FIVE:
        assert name in warning
    _assert_no_values(warning)


@pytest.mark.parametrize(
    ("changed", "still_default"),
    [
        (["demo_admin_password"], ALL_FIVE[1:]),
        (
            ["postgres_password", "session_cookie_secure"],
            ["DEMO_ADMIN_PASSWORD", "DEMO_EDITOR_PASSWORD", "DEMO_VIEWER_PASSWORD"],
        ),
        (
            [
                "demo_admin_password",
                "demo_editor_password",
                "demo_viewer_password",
                "postgres_password",
            ],
            ["SESSION_COOKIE_SECURE"],
        ),
    ],
)
def test_partial_changes_name_only_the_remaining_defaults(
    changed: list[str], still_default: list[str]
) -> None:
    settings = Settings(sanad_env="production", **{k: CHANGED[k] for k in changed})  # type: ignore[arg-type]

    with pytest.raises(InsecureDefaultsError) as caught:
        check_public_defaults(settings, log)

    assert caught.value.names == still_default


def test_settings_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SANAD_ENV", "production")
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "a-real-admin-secret")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")

    with pytest.raises(InsecureDefaultsError) as caught:
        check_public_defaults(Settings(), log)

    assert caught.value.names == [
        "DEMO_EDITOR_PASSWORD",
        "DEMO_VIEWER_PASSWORD",
        "POSTGRES_PASSWORD",
    ]


def test_unknown_sanad_env_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SANAD_ENV", "prod")
    with pytest.raises(ValueError, match="sanad_env"):
        Settings()


# --- startup: init ----------------------------------------------------------------------------


def test_init_refuses_in_production_before_any_step(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("SANAD_ENV", "production")
    ran: list[Settings] = []
    monkeypatch.setattr(init, "run", ran.append)

    with pytest.raises(SystemExit) as exited:
        init.main()

    assert exited.value.code == 2
    assert ran == []
    critical = [r.getMessage() for r in caplog.records if r.levelno == logging.CRITICAL]
    assert len(critical) == 1
    assert critical[0].startswith(INSECURE_DEFAULTS)
    for name in ALL_FIVE:
        assert name in critical[0]


def test_init_runs_in_demo_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    ran: list[Settings] = []
    monkeypatch.setattr(init, "run", ran.append)

    init.main()

    assert len(ran) == 1
    assert any(
        r.levelno == logging.WARNING and "SESSION_COOKIE_SECURE" in r.getMessage()
        for r in caplog.records
    )


# --- startup: api -----------------------------------------------------------------------------


def test_api_refuses_to_start_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SANAD_ENV", "production")

    with pytest.raises(InsecureDefaultsError) as caught, TestClient(create_app()):
        pass

    assert caught.value.names == ALL_FIVE


def test_api_starts_in_demo_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    with TestClient(create_app()) as client:
        assert client.app is not None

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("DEMO_ADMIN_PASSWORD" in w for w in warnings)
