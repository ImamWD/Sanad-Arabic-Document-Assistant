from fastapi.testclient import TestClient

from tests.api.conftest import Sessions, as_


def test_get_me_matches_the_shell_contract(client: TestClient, sessions: Sessions) -> None:
    response = client.get("/api/me", headers=as_(sessions["admin"]))

    assert response.status_code == 200
    me = response.json()
    assert set(me) == {"id", "name", "email", "role", "preferred_language", "is_guest"}
    assert me | {"id": None} == {
        "id": None,
        "name": "Demo Admin",
        "email": "admin@sanad.example",
        "role": "admin",
        "preferred_language": "en",
        "is_guest": False,
    }


def test_patch_me_saves_the_language(client: TestClient, sessions: Sessions) -> None:
    headers = as_(sessions["viewer"])

    response = client.patch("/api/me", json={"preferred_language": "ar"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["preferred_language"] == "ar"
    assert client.get("/api/me", headers=headers).json()["preferred_language"] == "ar"


def test_guest_cannot_patch_me(client: TestClient, sessions: Sessions) -> None:
    headers = as_(sessions["guest"])

    response = client.patch("/api/me", json={"preferred_language": "ar"}, headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert client.get("/api/me", headers=headers).json()["preferred_language"] == "en"


def test_patch_me_accepts_only_the_language(client: TestClient, sessions: Sessions) -> None:
    headers = as_(sessions["viewer"])
    for body in ({"preferred_language": "fr"}, {"role": "admin"}, {}):
        response = client.patch("/api/me", json=body, headers=headers)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.get("/api/me", headers=headers).json()["role"] == "viewer"
