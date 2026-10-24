import pytest
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from sanad.core.config import Settings

AWKWARD_PASSWORD = "p@ss:w/rd#?%&= x"  # noqa: S105 - test value, every URL-special character


def test_database_url_survives_url_special_characters_in_password() -> None:
    settings = Settings(postgres_password=SecretStr(AWKWARD_PASSWORD))

    rendered = settings.database_url.render_as_string(hide_password=False)
    parsed = make_url(rendered)

    assert parsed.password == AWKWARD_PASSWORD
    assert (parsed.username, parsed.host, parsed.port, parsed.database) == (
        settings.postgres_user,
        settings.postgres_host,
        settings.postgres_port,
        settings.postgres_db,
    )
    assert parsed.drivername == "postgresql+psycopg"


def test_database_url_never_shows_the_password_by_default() -> None:
    settings = Settings(postgres_password=SecretStr(AWKWARD_PASSWORD))
    assert AWKWARD_PASSWORD not in str(settings.database_url)
    assert AWKWARD_PASSWORD not in repr(settings)


def test_settings_read_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "pg.internal")
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    monkeypatch.setenv("ML_BASE_URL", "http://ml-alt:9000")

    settings = Settings()

    assert settings.database_url.host == "pg.internal"
    assert settings.database_url.port == 6543
    assert settings.ml_base_url == "http://ml-alt:9000"
