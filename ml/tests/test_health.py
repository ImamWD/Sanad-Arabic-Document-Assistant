import os

from fastapi.testclient import TestClient

from sanad_ml.main import create_app
from tests.fakes import FakeEngine


def test_health_ok_once_models_are_loaded() -> None:
    with TestClient(create_app(FakeEngine)) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "embed_model": "fake/embed@test",
        "rerank_model": "fake/rerank@test",
    }


def test_hub_is_offline() -> None:
    # Weights must come from the image, never from the network at runtime.
    assert os.environ.get("HF_HUB_OFFLINE") == "1"
