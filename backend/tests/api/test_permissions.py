"""Permission matrix: every API route, called by every principal.

Append-only (ROADMAP "File ownership"): a task that adds a route adds its row to MATRIX, or
to PUBLIC if it needs no session. `test_every_route_is_covered` fails until it does.

A row lists the principals allowed past authorisation; with the row's body they must get a
2xx. Everyone else gets 401 UNAUTHENTICATED (anonymous) or 403 FORBIDDEN (signed in).
`path` is the route template; `fill` maps each {placeholder} to a key of the `ids` fixture.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient

from tests.api.conftest import PRINCIPALS, Sessions, as_

GUEST, VIEWER, EDITOR, ADMIN = "guest", "viewer", "editor", "admin"
STAFF = frozenset({VIEWER, EDITOR, ADMIN})
SIGNED_IN = STAFF | {GUEST}
EDITORS = frozenset({EDITOR, ADMIN})
ADMINS = frozenset({ADMIN})


@dataclass(frozen=True)
class Row:
    method: str
    path: str
    allowed: frozenset[str]
    body: dict[str, Any] = field(default_factory=dict)
    fill: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.method} {self.path}"


MATRIX: list[Row] = [
    # --- B2 ---
    Row("GET", "/api/me", SIGNED_IN),
    Row("PATCH", "/api/me", STAFF, {"preferred_language": "ar"}),
    Row("GET", "/api/programmes", SIGNED_IN),
    Row("GET", "/api/admin/users", ADMINS),
    Row(
        "POST",
        "/api/admin/users",
        ADMINS,
        {
            "name": "Matrix Probe",
            "email": "matrix.probe@sanad.example",
            "password": "matrix-probe-2026",
            "role": "viewer",
            "preferred_language": "en",
        },
    ),
    Row(
        "PATCH",
        "/api/admin/users/{user_id}",
        ADMINS,
        {"preferred_language": "ar"},
        fill={"user_id": "viewer_id"},
    ),
]

# Routes that need no session.
PUBLIC: set[tuple[str, str]] = {
    ("GET", "/api/health"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/guest"),
    ("POST", "/api/auth/logout"),
}


def test_every_route_is_covered(app: FastAPI) -> None:
    routes = {
        (method, route.path)
        for route in iter_route_contexts(app.routes)
        if isinstance(route.original_route, APIRoute) and route.path and route.methods
        for method in route.methods
    }
    covered = {(row.method, row.path) for row in MATRIX} | PUBLIC
    assert routes - covered == set(), "add these routes to MATRIX or PUBLIC"
    assert covered - routes == set(), "MATRIX or PUBLIC lists routes that don't exist"


@pytest.mark.parametrize("who", PRINCIPALS)
@pytest.mark.parametrize("row", MATRIX, ids=str)
def test_permission_matrix(
    client: TestClient, sessions: Sessions, ids: dict[str, uuid.UUID], row: Row, who: str
) -> None:
    response = client.request(
        row.method,
        row.path.format(**{name: ids[key] for name, key in row.fill.items()}),
        headers=as_(sessions.get(who)),
        json=None if row.method == "GET" else row.body,
    )

    if who in row.allowed:
        assert 200 <= response.status_code < 300, response.text
    elif who == "anonymous":
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    else:
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"
