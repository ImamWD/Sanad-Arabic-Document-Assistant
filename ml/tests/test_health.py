import os

from fastapi.testclient import TestClient

from sanad_ml.main import app


def test_health_ok() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_hub_is_offline() -> None:
    # Weights must come from the image, never from the network at runtime.
    assert os.environ.get("HF_HUB_OFFLINE") == "1"
