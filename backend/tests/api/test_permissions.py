"""Permission matrix: every API route, called by every principal.

Append-only (ROADMAP "File ownership"): a task that adds a route adds its row to MATRIX, or
to PUBLIC if it needs no session. `test_every_route_is_covered` fails until it does.

A row lists the principals allowed past authorisation; with the row's body they must get a
2xx. Everyone else gets 401 UNAUTHENTICATED (anonymous) or 403 FORBIDDEN (signed in).
`path` is the route template; `fill` maps each {placeholder} to a key of the `ids` fixture.
A row with `files` is sent as multipart, with `body` as its form fields; otherwise the body is
JSON (none for GET).
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient

from sanad.api.main import create_app
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
    # Multipart file parts: {"file": ("report.pdf", b"%PDF-…", "application/pdf")}.
    files: dict[str, tuple[str, bytes, str]] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.method} {self.path}"


def send(
    client: TestClient, row: Row, headers: dict[str, str], ids: dict[str, uuid.UUID]
) -> httpx2.Response:
    path = row.path.format(**{name: ids[key] for name, key in row.fill.items()})
    if row.method == "GET":
        return client.request(row.method, path, headers=headers)
    if row.files:
        return client.request(row.method, path, headers=headers, data=row.body, files=row.files)
    return client.request(row.method, path, headers=headers, json=row.body)


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
    # --- B3 ---
    Row("GET", "/api/documents", SIGNED_IN),
    Row("GET", "/api/documents/{document_id}", SIGNED_IN, fill={"document_id": "document_id"}),
    Row(
        "GET",
        "/api/documents/{document_id}/file",
        SIGNED_IN,
        fill={"document_id": "document_id"},
    ),
    Row(
        "GET",
        "/api/documents/{document_id}/pages/{page_number}",
        SIGNED_IN,
        fill={"document_id": "document_id", "page_number": "page_one"},
    ),
    Row(
        "PATCH",
        "/api/documents/{document_id}",
        EDITORS,
        {"tags": ["matrix"]},
        fill={"document_id": "document_id"},
    ),
    Row(
        "POST",
        "/api/documents/{document_id}/archive",
        EDITORS,
        fill={"document_id": "document_id"},
    ),
    Row(
        "POST",
        "/api/documents/{document_id}/unarchive",
        EDITORS,
        fill={"document_id": "document_id"},
    ),
    Row(
        "POST",
        "/api/documents/{document_id}/retry",
        EDITORS,
        fill={"document_id": "failed_document_id"},
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
    response = send(client, row, as_(sessions.get(who)), ids)

    if who in row.allowed:
        assert 200 <= response.status_code < 300, response.text
    elif who == "anonymous":
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    else:
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"


def test_send_builds_each_body_kind() -> None:
    """`send` on a probe app (so MATRIX never sees it): multipart rows pass the CSRF guard."""
    probe_app = create_app()

    @probe_app.api_route("/api/__echo", methods=["GET", "POST"])
    async def echo(request: Request) -> dict[str, Any]:
        body = (await request.body()).decode()
        return {"content_type": request.headers.get("content-type"), "body": body}

    rows = {
        "GET": Row("GET", "/api/__echo", frozenset()),
        "json": Row("POST", "/api/__echo", frozenset(), {"title": "تقرير"}),
        "multipart": Row(
            "POST",
            "/api/__echo",
            frozenset(),
            {"title": "Annual report", "year": 2023, "restricted": False},
            files={"file": ("report.pdf", b"%PDF-1.7 probe", "application/pdf")},
        ),
    }
    with TestClient(probe_app, raise_server_exceptions=False) as client:
        sent = {kind: send(client, row, as_(None), {}) for kind, row in rows.items()}

    assert all(r.status_code == 200 for r in sent.values()), {k: r.text for k, r in sent.items()}
    assert sent["GET"].json() == {"content_type": None, "body": ""}
    assert sent["json"].json()["content_type"] == "application/json"
    multipart = sent["multipart"].json()
    assert multipart["content_type"].startswith("multipart/form-data; boundary=")
    for part in ('name="title"', "Annual report", 'name="year"', "2023", 'filename="report.pdf"'):
        assert part in multipart["body"]


# --- B3: documents for the rows above ------------------------------------------------------------


@pytest.fixture
def ids(
    ids: dict[str, Any], engine: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict[str, Any]]:
    """B2's ids plus a ready seed document (with its PDF and page 1) and a failed one."""
    from sqlalchemy import insert as sql_insert
    from sqlalchemy import select as sql_select

    from sanad.core.models import User
    from sanad.documents.models import Document, DocumentPage
    from sanad.ingest.settings import get_ingest_settings

    monkeypatch.setenv("FILES_DIR", str(tmp_path))
    get_ingest_settings.cache_clear()
    (tmp_path / "originals").mkdir()
    rows = []
    with engine.begin() as conn:
        editor = conn.scalar(sql_select(User.id).where(User.email == "editor@sanad.example"))
        for status in ("ready", "failed"):
            document_id = uuid.uuid4()
            (tmp_path / "originals" / f"{document_id}.pdf").write_bytes(b"%PDF-1.4 matrix")
            rows.append(
                {
                    "id": document_id,
                    "title": f"Matrix {status}",
                    "title_norm": f"matrix {status}",
                    "original_filename": "matrix.pdf",
                    "file_path": f"originals/{document_id}.pdf",
                    "viewer_path": f"originals/{document_id}.pdf",
                    "file_type": "pdf",
                    "uploaded_by": editor,
                    "status": status,
                    "error_code": "FILE_CORRUPT" if status == "failed" else None,
                    "page_count": 1,
                    "sha256": uuid.uuid4().hex * 2,
                    "size_bytes": 15,
                    "is_seed": True,
                }
            )
        conn.execute(sql_insert(Document), rows)
        conn.execute(
            sql_insert(DocumentPage).values(
                document_id=rows[0]["id"], page_number=1, text="", text_norm="", char_count=0
            )
        )
    yield {
        **ids,
        "document_id": rows[0]["id"],
        "failed_document_id": rows[1]["id"],
        "page_one": 1,
    }
    get_ingest_settings.cache_clear()
