import json

import sqlalchemy
from fastapi.testclient import TestClient
from sqlalchemy import text

from sanad.core.config import Settings
from tests.api.conftest import Sessions, as_


def _manifest_programmes(settings: Settings) -> list[dict[str, str]]:
    manifest = json.loads((settings.seed_dir / "manifest.json").read_text(encoding="utf-8"))
    return sorted(
        ({k: p[k] for k in ("code", "name_ar", "name_en")} for p in manifest["programmes"]),
        key=lambda p: p["code"],
    )


def test_programmes_come_from_the_seed_manifest(
    client: TestClient, sessions: Sessions, settings: Settings
) -> None:
    response = client.get("/api/programmes", headers=as_(sessions["guest"]))

    assert response.status_code == 200
    programmes = response.json()
    assert len(programmes) == 6
    assert [{k: p[k] for k in ("code", "name_ar", "name_en")} for p in programmes] == (
        _manifest_programmes(settings)
    )
    assert all(set(p) == {"id", "code", "name_ar", "name_en"} for p in programmes)


def test_inactive_programmes_are_hidden(
    client: TestClient, sessions: Sessions, engine: sqlalchemy.Engine
) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE programmes SET is_active = false WHERE code = 'WASH'"))
    codes = [
        p["code"] for p in client.get("/api/programmes", headers=as_(sessions["viewer"])).json()
    ]
    assert "WASH" not in codes
    assert len(codes) == 5
