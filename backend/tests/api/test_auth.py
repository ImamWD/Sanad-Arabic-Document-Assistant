"""Login, logout, guest login, sessions, rate limiting and the CSRF guard."""

from collections.abc import Callable

import httpx2
import pytest
import sqlalchemy
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from sanad.core.config import Settings
from sanad.core.ratelimit import LoginRateLimiter
from sanad.core.security import SESSION_COOKIE
from tests.api.conftest import CSRF, Sessions, as_, demo_password, sign_in


def _login(client: TestClient, email: str, password: str, **headers: str) -> int:
    client.cookies.clear()
    response = client.post(
        "/api/auth/login", json={"email": email, "password": password}, headers=CSRF | headers
    )
    client.cookies.clear()
    return response.status_code


def _code(response: httpx2.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


# --- login -------------------------------------------------------------------------------


def test_login_returns_me_and_sets_a_hardened_cookie(
    client: TestClient, settings: Settings
) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "editor@sanad.example", "password": demo_password(settings, "editor")},
        headers=CSRF,
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "name", "email", "role", "preferred_language", "is_guest"}
    assert (body["email"], body["role"], body["is_guest"]) == (
        "editor@sanad.example",
        "editor",
        False,
    )
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/api" in cookie
    assert "Secure" not in cookie  # SESSION_COOKIE_SECURE defaults to false (plain http)


def test_secure_cookie_when_configured(
    client: TestClient, settings: Settings, set_env: Callable[..., None]
) -> None:
    set_env(session_cookie_secure="true")
    response = client.post(
        "/api/auth/login",
        json={"email": "viewer@sanad.example", "password": demo_password(settings, "viewer")},
        headers=CSRF,
    )
    assert "Secure" in response.headers["set-cookie"]


def test_session_cookie_opens_me(client: TestClient, sessions: Sessions) -> None:
    response = client.get("/api/me", headers=as_(sessions["viewer"]))
    assert response.status_code == 200
    assert response.json()["role"] == "viewer"


def test_email_is_case_insensitive(client: TestClient, settings: Settings) -> None:
    assert _login(client, "  Admin@Sanad.Example ", demo_password(settings, "admin")) == 200


@pytest.mark.parametrize(
    ("email", "password"),
    [("viewer@sanad.example", "wrong-password"), ("nobody@sanad.example", "whatever-it-is")],
)
def test_bad_credentials_are_one_code(client: TestClient, email: str, password: str) -> None:
    response = client.post(
        "/api/auth/login", json={"email": email, "password": password}, headers=CSRF
    )
    assert response.status_code == 401
    assert _code(response) == "INVALID_CREDENTIALS"
    assert SESSION_COOKIE not in response.cookies


def test_guest_cannot_log_in_with_a_password(client: TestClient) -> None:
    assert _login(client, "guest@sanad.example", "!") == 401


def test_failed_login_is_audited(client: TestClient, engine: sqlalchemy.Engine) -> None:
    _login(client, "viewer@sanad.example", "wrong-password")
    with engine.connect() as conn:
        actions = conn.scalars(text("SELECT action FROM audit_events")).all()
    assert actions == ["auth.login_failed"]


def test_login_replaces_the_browser_session(
    client: TestClient, settings: Settings, engine: sqlalchemy.Engine
) -> None:
    first = sign_in(client, settings, "viewer")
    response = client.post(
        "/api/auth/login",
        json={"email": "viewer@sanad.example", "password": demo_password(settings, "viewer")},
        headers=as_(first),
    )
    assert response.status_code == 200
    assert client.get("/api/me", headers=as_(first)).status_code == 401
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM sessions")) == 1


def test_login_upgrades_an_outdated_hash(
    client: TestClient, settings: Settings, engine: sqlalchemy.Engine
) -> None:
    password = demo_password(settings, "viewer")
    old_hash = PasswordHasher(time_cost=2, memory_cost=16, parallelism=1).hash(password)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET password_hash = :h WHERE email = 'viewer@sanad.example'"),
            {"h": old_hash},
        )

    assert _login(client, "viewer@sanad.example", password) == 200

    with engine.connect() as conn:
        new_hash = conn.scalar(
            text("SELECT password_hash FROM users WHERE email = 'viewer@sanad.example'")
        )
    assert new_hash != old_hash
    assert new_hash.startswith("$argon2id$")


# --- logout and session lifetime --------------------------------------------------------


def test_logout_ends_the_session(client: TestClient, sessions: Sessions) -> None:
    token = sessions["editor"]
    response = client.post("/api/auth/logout", json={}, headers=as_(token))

    assert response.status_code == 204
    assert f"{SESSION_COOKIE}=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    me = client.get("/api/me", headers=as_(token))
    assert me.status_code == 401
    assert _code(me) == "UNAUTHENTICATED"


def test_logout_without_a_session_is_fine(client: TestClient) -> None:
    assert client.post("/api/auth/logout", json={}, headers=CSRF).status_code == 204
    assert client.post("/api/auth/logout", json={}, headers=as_("not-a-token")).status_code == 204


def test_unknown_token_is_unauthenticated(client: TestClient) -> None:
    response = client.get("/api/me", headers=as_("forged-token"))
    assert response.status_code == 401
    assert _code(response) == "UNAUTHENTICATED"


@pytest.mark.parametrize(
    "expire_sql",
    [
        "UPDATE sessions SET last_seen_at = now() - interval '481 minutes'",  # idle
        "UPDATE sessions SET expires_at = now() - interval '1 second'",  # absolute
    ],
    ids=["idle", "absolute"],
)
def test_expired_session_is_rejected_and_removed(
    client: TestClient, sessions: Sessions, engine: sqlalchemy.Engine, expire_sql: str
) -> None:
    with engine.begin() as conn:
        conn.execute(text(expire_sql))

    assert client.get("/api/me", headers=as_(sessions["viewer"])).status_code == 401

    with engine.connect() as conn:
        remaining = conn.scalar(
            text(
                "SELECT count(*) FROM sessions s JOIN users u ON u.id = s.user_id"
                " WHERE u.email = 'viewer@sanad.example'"
            )
        )
    assert remaining == 0


def test_activity_refreshes_last_seen(
    client: TestClient, sessions: Sessions, engine: sqlalchemy.Engine
) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE sessions SET last_seen_at = now() - interval '2 hours'"))

    assert client.get("/api/me", headers=as_(sessions["viewer"])).status_code == 200

    with engine.connect() as conn:
        stale = conn.scalar(
            text("SELECT count(*) FROM sessions WHERE last_seen_at < now() - interval '1 hour'")
        )
    assert stale == len(sessions) - 1  # only the viewer's session was used


def test_new_logins_sweep_expired_sessions(
    client: TestClient, settings: Settings, sessions: Sessions, engine: sqlalchemy.Engine
) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE sessions SET expires_at = now() - interval '1 second'"))
    sign_in(client, settings, "admin")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM sessions")) == 1


# --- guest -------------------------------------------------------------------------------


def test_guest_login(client: TestClient) -> None:
    response = client.post("/api/auth/guest", json={}, headers=CSRF)
    assert response.status_code == 200
    me = response.json()
    assert (me["role"], me["is_guest"], me["preferred_language"]) == ("viewer", True, "en")
    assert SESSION_COOKIE in response.cookies


def test_guest_mode_off_refuses_login_and_existing_sessions(
    client: TestClient, sessions: Sessions, set_env: Callable[..., None]
) -> None:
    set_env(guest_mode="off")

    response = client.post("/api/auth/guest", json={}, headers=CSRF)
    assert response.status_code == 403
    assert _code(response) == "GUEST_DISABLED"
    assert client.get("/api/me", headers=as_(sessions["guest"])).status_code == 401
    assert client.get("/api/me", headers=as_(sessions["viewer"])).status_code == 200


def test_deactivated_guest_is_disabled(
    client: TestClient, sessions: Sessions, engine: sqlalchemy.Engine
) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET is_active = false WHERE is_guest"))
    response = client.post("/api/auth/guest", json={}, headers=CSRF)
    assert response.status_code == 403
    assert _code(response) == "GUEST_DISABLED"
    assert client.get("/api/me", headers=as_(sessions["guest"])).status_code == 401


def test_missing_guest_account_is_disabled(client: TestClient, engine: sqlalchemy.Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE is_guest"))
    assert client.post("/api/auth/guest", json={}, headers=CSRF).status_code == 403


# --- deactivation ------------------------------------------------------------------------


def test_deactivated_user_cannot_log_in(
    client: TestClient, settings: Settings, engine: sqlalchemy.Engine
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET is_active = false WHERE email = 'editor@sanad.example'")
        )

    response = client.post(
        "/api/auth/login",
        json={"email": "editor@sanad.example", "password": demo_password(settings, "editor")},
        headers=CSRF,
    )
    assert response.status_code == 403
    assert _code(response) == "ACCOUNT_DISABLED"
    # A wrong password still says only "invalid credentials".
    assert _login(client, "editor@sanad.example", "wrong-password") == 401


def test_inactive_user_with_a_live_session_is_rejected(
    client: TestClient, sessions: Sessions, engine: sqlalchemy.Engine
) -> None:
    # Deactivation through the API also deletes sessions; this checks the second lock alone.
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET is_active = false WHERE email = 'editor@sanad.example'")
        )
    assert client.get("/api/me", headers=as_(sessions["editor"])).status_code == 401


# --- rate limiting -----------------------------------------------------------------------


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(app: FastAPI, settings: Settings) -> FakeClock:
    fake = FakeClock()
    app.state.login_limiter = LoginRateLimiter(
        window_seconds=settings.login_window_seconds,
        max_failures_per_email=settings.login_max_failures_per_email,
        max_failures_per_ip=settings.login_max_failures_per_ip,
        clock=fake,
    )
    return fake


def test_too_many_failures_lock_the_email(
    client: TestClient, settings: Settings, clock: FakeClock
) -> None:
    right = demo_password(settings, "viewer")
    for _ in range(settings.login_max_failures_per_email):
        assert _login(client, "viewer@sanad.example", "wrong-password") == 401

    response = client.post(
        "/api/auth/login",
        json={"email": "VIEWER@sanad.example", "password": right},
        headers=CSRF,
    )
    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "code": "RATE_LIMITED",
            "params": {"retry_after_seconds": settings.login_window_seconds},
        }
    }
    # Other accounts are unaffected.
    assert _login(client, "editor@sanad.example", demo_password(settings, "editor")) == 200

    clock.now += settings.login_window_seconds
    assert _login(client, "viewer@sanad.example", right) == 200


def test_success_clears_the_failure_count(
    client: TestClient, settings: Settings, clock: FakeClock
) -> None:
    right = demo_password(settings, "viewer")
    for _ in range(settings.login_max_failures_per_email - 1):
        _login(client, "viewer@sanad.example", "wrong-password")
    assert _login(client, "viewer@sanad.example", right) == 200
    assert _login(client, "viewer@sanad.example", "wrong-password") == 401
    assert _login(client, "viewer@sanad.example", right) == 200


def test_too_many_failures_from_one_ip_lock_that_ip(
    client: TestClient, settings: Settings, clock: FakeClock
) -> None:
    attacker = {"X-Real-IP": "203.0.113.9"}
    for n in range(settings.login_max_failures_per_ip):
        assert _login(client, f"spray{n}@sanad.example", "guess-1234", **attacker) == 401

    admin_password = demo_password(settings, "admin")
    assert _login(client, "admin@sanad.example", admin_password, **attacker) == 429
    assert (
        _login(client, "admin@sanad.example", admin_password, **{"X-Real-IP": "198.51.100.4"})
        == 200
    )


# --- CSRF --------------------------------------------------------------------------------


def _credentials(settings: Settings) -> dict[str, str]:
    return {"email": "viewer@sanad.example", "password": demo_password(settings, "viewer")}


def test_state_change_without_the_header_is_rejected(
    client: TestClient, settings: Settings
) -> None:
    response = client.post("/api/auth/login", json=_credentials(settings))
    assert response.status_code == 403
    assert _code(response) == "CSRF_REJECTED"


@pytest.mark.parametrize("content_type", ["text/plain", "application/x-www-form-urlencoded", None])
def test_state_change_with_a_form_content_type_is_rejected(
    client: TestClient, content_type: str | None
) -> None:
    headers = dict(CSRF)
    if content_type:
        headers["Content-Type"] = content_type
    response = client.post("/api/auth/guest", content=b"{}", headers=headers)
    assert response.status_code == 403
    assert _code(response) == "CSRF_REJECTED"


def test_csrf_is_checked_before_authentication(client: TestClient) -> None:
    assert _code(client.patch("/api/me", json={"preferred_language": "ar"})) == "CSRF_REJECTED"


@pytest.mark.parametrize(
    "content_type", ["application/json; charset=utf-8", "multipart/form-data; boundary=x"]
)
def test_json_and_multipart_pass_the_guard(client: TestClient, content_type: str) -> None:
    # The guest route ignores its body, so any well-formed request reaches it.
    response = client.post(
        "/api/auth/guest", content=b"{}", headers=CSRF | {"Content-Type": content_type}
    )
    assert response.status_code == 200


def test_reads_need_no_header(client: TestClient, sessions: Sessions) -> None:
    response = client.get("/api/me", headers={"Cookie": f"{SESSION_COOKIE}={sessions['viewer']}"})
    assert response.status_code == 200


def test_unknown_routes_and_methods_keep_their_codes(client: TestClient) -> None:
    assert _code(client.post("/api/nowhere", json={})) == "NOT_FOUND"
    assert _code(client.delete("/api/me")) == "METHOD_NOT_ALLOWED"
