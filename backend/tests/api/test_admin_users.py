import uuid
from typing import Any

import pytest
import sqlalchemy
from fastapi.testclient import TestClient
from sqlalchemy import text

from sanad.core.config import Settings
from tests.api.conftest import CSRF, Sessions, as_

NEW_USER = {
    "name": "سلمى التجريبية",
    "email": "salma.demo@sanad.example",
    "password": "a-long-enough-password",
    "role": "editor",
    "preferred_language": "ar",
}


def _create(client: TestClient, sessions: Sessions, **overrides: Any) -> Any:
    return client.post(
        "/api/admin/users", json=NEW_USER | overrides, headers=as_(sessions["admin"])
    )


def _patch(client: TestClient, sessions: Sessions, user_id: uuid.UUID, **body: Any) -> Any:
    return client.patch(f"/api/admin/users/{user_id}", json=body, headers=as_(sessions["admin"]))


def test_list_users(client: TestClient, sessions: Sessions) -> None:
    response = client.get("/api/admin/users", headers=as_(sessions["admin"]))

    assert response.status_code == 200
    users = {u["email"]: u for u in response.json()}
    assert set(users) == {
        "admin@sanad.example",
        "editor@sanad.example",
        "viewer@sanad.example",
        "guest@sanad.example",
    }
    assert set(users["guest@sanad.example"]) == {
        "id", "name", "email", "role", "preferred_language", "is_active", "is_guest",
        "created_at", "updated_at", "last_login_at",
    }  # fmt: skip
    assert users["guest@sanad.example"]["is_guest"] is True
    assert users["admin@sanad.example"]["last_login_at"] is not None
    assert all("password" not in key for u in users.values() for key in u)


def test_create_user_who_can_then_log_in(
    client: TestClient, sessions: Sessions, engine: sqlalchemy.Engine
) -> None:
    response = _create(client, sessions)

    assert response.status_code == 201
    created = response.json()
    assert (created["name"], created["role"], created["is_active"], created["is_guest"]) == (
        "سلمى التجريبية", "editor", True, False,
    )  # fmt: skip
    login = client.post(
        "/api/auth/login",
        json={"email": "salma.demo@sanad.example", "password": "a-long-enough-password"},
        headers=CSRF,
    )
    assert login.status_code == 200
    assert login.json()["preferred_language"] == "ar"
    with engine.connect() as conn:
        stored = conn.scalar(
            text("SELECT password_hash FROM users WHERE email = 'salma.demo@sanad.example'")
        )
        audit = conn.execute(
            text("SELECT action, target_id, meta FROM audit_events WHERE action = 'user.create'")
        ).one()
    assert stored.startswith("$argon2id$")
    assert str(audit.target_id) == created["id"]
    assert audit.meta == {"role": "editor"}


@pytest.mark.parametrize("email", ["salma.demo@sanad.example", "Viewer@Sanad.example"])
def test_duplicate_email_is_refused(client: TestClient, sessions: Sessions, email: str) -> None:
    _create(client, sessions)
    response = _create(client, sessions, email=email)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_TAKEN"


def test_short_password_is_refused_with_the_minimum(client: TestClient, sessions: Sessions) -> None:
    response = _create(client, sessions, password="short")  # noqa: S106
    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "PASSWORD_TOO_SHORT", "params": {"min_length": 10}}
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "not-an-email"},
        {"name": "   "},
        {"role": "superuser"},
        {"preferred_language": "fr"},
        {"is_guest": True},
    ],
)
def test_invalid_create_bodies(
    client: TestClient, sessions: Sessions, overrides: dict[str, Any]
) -> None:
    response = _create(client, sessions, **overrides)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_edit_role_and_language(
    client: TestClient, sessions: Sessions, ids: dict[str, uuid.UUID], engine: sqlalchemy.Engine
) -> None:
    response = _patch(client, sessions, ids["viewer_id"], role="editor", preferred_language="ar")

    assert response.status_code == 200
    assert (response.json()["role"], response.json()["preferred_language"]) == ("editor", "ar")
    # The new role applies to the user's existing session at once.
    me = client.get("/api/me", headers=as_(sessions["viewer"])).json()
    assert me["role"] == "editor"
    with engine.connect() as conn:
        meta = conn.scalar(text("SELECT meta FROM audit_events WHERE action = 'user.update'"))
    assert meta == {"role": ["viewer", "editor"], "preferred_language": ["en", "ar"]}


def test_unchanged_edit_writes_no_audit_event(
    client: TestClient, sessions: Sessions, ids: dict[str, uuid.UUID], engine: sqlalchemy.Engine
) -> None:
    assert _patch(client, sessions, ids["viewer_id"], role="viewer").status_code == 200
    with engine.connect() as conn:
        assert (
            conn.scalar(text("SELECT count(*) FROM audit_events WHERE action = 'user.update'")) == 0
        )


def test_deactivation_signs_the_user_out_and_blocks_login(
    client: TestClient, sessions: Sessions, ids: dict[str, uuid.UUID], settings: Settings
) -> None:
    response = _patch(client, sessions, ids["editor_id"], is_active=False)

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert client.get("/api/me", headers=as_(sessions["editor"])).status_code == 401
    password = settings.demo_editor_password.get_secret_value()
    login = client.post(
        "/api/auth/login",
        json={"email": "editor@sanad.example", "password": password},
        headers=CSRF,
    )
    assert login.status_code == 403
    assert login.json()["error"]["code"] == "ACCOUNT_DISABLED"

    assert _patch(client, sessions, ids["editor_id"], is_active=True).status_code == 200
    client.cookies.clear()
    login = client.post(
        "/api/auth/login",
        json={"email": "editor@sanad.example", "password": password},
        headers=CSRF,
    )
    assert login.status_code == 200


@pytest.mark.parametrize("body", [{"role": "editor"}, {"role": "viewer"}, {"is_active": False}])
def test_admin_cannot_lock_themselves_out(
    client: TestClient, sessions: Sessions, ids: dict[str, uuid.UUID], body: dict[str, Any]
) -> None:
    response = _patch(client, sessions, ids["admin_id"], **body)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CANNOT_CHANGE_OWN_ACCESS"


def test_admin_can_edit_their_own_name_and_language(
    client: TestClient, sessions: Sessions, ids: dict[str, uuid.UUID]
) -> None:
    response = _patch(
        client, sessions, ids["admin_id"], name="Demo Admin (AR)", preferred_language="ar",
        role="admin", is_active=True,
    )  # fmt: skip
    assert response.status_code == 200
    assert response.json()["name"] == "Demo Admin (AR)"


@pytest.mark.parametrize("role", ["editor", "admin"])
def test_guest_role_is_fixed(
    client: TestClient, sessions: Sessions, ids: dict[str, uuid.UUID], role: str
) -> None:
    response = _patch(client, sessions, ids["guest_id"], role=role)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GUEST_ROLE_FIXED"
    assert client.get("/api/me", headers=as_(sessions["guest"])).json()["role"] == "viewer"


def test_admin_can_switch_the_guest_off(
    client: TestClient, sessions: Sessions, ids: dict[str, uuid.UUID]
) -> None:
    assert _patch(client, sessions, ids["guest_id"], is_active=False).status_code == 200
    assert client.get("/api/me", headers=as_(sessions["guest"])).status_code == 401
    guest = client.post("/api/auth/guest", json={}, headers=CSRF)
    assert guest.json()["error"]["code"] == "GUEST_DISABLED"


def test_unknown_user_is_not_found(client: TestClient, sessions: Sessions) -> None:
    response = _patch(client, sessions, uuid.uuid4(), name="Nobody")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_users_are_never_deleted(
    client: TestClient, sessions: Sessions, ids: dict[str, uuid.UUID]
) -> None:
    response = client.delete(f"/api/admin/users/{ids['viewer_id']}", headers=as_(sessions["admin"]))
    assert response.status_code == 405
