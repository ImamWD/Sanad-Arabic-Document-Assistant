from fastapi import FastAPI
from fastapi.testclient import TestClient

from sanad.api.main import create_app
from sanad.core.errors import ApiError, ErrorCode


def _app_with_probe_routes() -> FastAPI:
    app = create_app()

    @app.get("/api/__boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    @app.get("/api/__coded")
    async def coded() -> None:
        raise ApiError(409, ErrorCode.BAD_REQUEST, field="title")

    @app.get("/api/__typed")
    async def typed(n: int) -> int:
        return n

    return app


client = TestClient(_app_with_probe_routes(), raise_server_exceptions=False)


def test_unknown_route_returns_code_not_prose() -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "params": {}}}


def test_wrong_method_returns_code() -> None:
    response = client.post("/api/health")
    assert response.status_code == 405
    assert response.json() == {"error": {"code": "METHOD_NOT_ALLOWED", "params": {}}}


def test_validation_error_lists_fields_only() -> None:
    response = client.get("/api/__typed", params={"n": "not-a-number"})
    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "VALIDATION_ERROR", "params": {"fields": ["query.n"]}}
    }


def test_api_error_carries_status_and_params() -> None:
    response = client.get("/api/__coded")
    assert response.status_code == 409
    assert response.json() == {"error": {"code": "BAD_REQUEST", "params": {"field": "title"}}}


def test_unhandled_exception_hides_details() -> None:
    response = client.get("/api/__boom")
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "INTERNAL_ERROR", "params": {}}}
    assert "secret" not in response.text
    assert "Traceback" not in response.text
