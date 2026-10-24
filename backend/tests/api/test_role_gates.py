"""require_role over HTTP (cookie → get_current_user → require_role), on probe routes.

No editor-only route exists in B2, so the permission matrix can't show that the guest and
viewers are kept out of one. These probes live on a separate app, so the route-coverage
check in test_permissions.py never sees them.
"""

from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from sanad.api.main import create_app
from sanad.core.config import Settings
from sanad.core.security import Role, User, require_role
from tests.api.conftest import PRINCIPALS, as_, sign_in

ALLOWED = {
    "/api/__editor_probe": {"editor", "admin"},
    "/api/__admin_probe": {"admin"},
    "/api/__viewer_probe": {"guest", "viewer", "editor", "admin"},
}


@pytest.fixture
def probe_client(seeded: None) -> Iterator[TestClient]:
    app = create_app()

    @app.post("/api/__editor_probe")
    async def editor_probe(
        user: Annotated[User, Depends(require_role(Role.EDITOR, Role.ADMIN))],
    ) -> str:
        return user.role

    @app.post("/api/__admin_probe")
    async def admin_probe(user: Annotated[User, Depends(require_role(Role.ADMIN))]) -> str:
        return user.role

    @app.post("/api/__viewer_probe")
    async def viewer_probe(
        user: Annotated[User, Depends(require_role(Role.VIEWER, Role.EDITOR, Role.ADMIN))],
    ) -> str:
        return user.role

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize("path", sorted(ALLOWED))
def test_role_gates(probe_client: TestClient, settings: Settings, path: str) -> None:
    tokens = {who: sign_in(probe_client, settings, who) for who in PRINCIPALS if who != "anonymous"}
    for who in PRINCIPALS:
        response = probe_client.post(path, json={}, headers=as_(tokens.get(who)))
        if who in ALLOWED[path]:
            assert response.status_code == 200, (who, response.text)
        elif who == "anonymous":
            assert (response.status_code, response.json()["error"]["code"]) == (
                401,
                "UNAUTHENTICATED",
            )
        else:
            assert (response.status_code, response.json()["error"]["code"]) == (
                403,
                "FORBIDDEN",
            ), who
