import asyncio
from collections.abc import Awaitable, Callable, Iterator

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from sanad.api import health as health_router
from sanad.api.main import create_app
from sanad.core.health import ProbeStatus, probe_db, probe_ml


def _fake_probe(status: ProbeStatus) -> Callable[..., Awaitable[ProbeStatus]]:
    async def probe(*_args: object) -> ProbeStatus:
        return status

    return probe


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def test_health_ok_matches_contract_byte_for_byte(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health_router, "probe_db", _fake_probe(ProbeStatus.OK))
    monkeypatch.setattr(health_router, "probe_ml", _fake_probe(ProbeStatus.OK))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.content == b'{"status":"ok","db":"ok","ml":"ok"}'


@pytest.mark.parametrize(
    ("db", "ml"),
    [
        (ProbeStatus.DOWN, ProbeStatus.OK),
        (ProbeStatus.OK, ProbeStatus.DOWN),
        (ProbeStatus.DOWN, ProbeStatus.DOWN),
    ],
)
def test_health_degraded_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: ProbeStatus, ml: ProbeStatus
) -> None:
    monkeypatch.setattr(health_router, "probe_db", _fake_probe(db))
    monkeypatch.setattr(health_router, "probe_ml", _fake_probe(ml))

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "db": db.value, "ml": ml.value}


def _ml_client(transport: httpx2.MockTransport) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(transport=transport)


def test_probe_ml_ok() -> None:
    transport = httpx2.MockTransport(lambda _req: httpx2.Response(200, json={"status": "ok"}))

    async def go() -> ProbeStatus:
        async with _ml_client(transport) as http:
            return await probe_ml(http, "http://ml:8001", timeout=1)

    assert asyncio.run(go()) == ProbeStatus.OK


@pytest.mark.parametrize(
    "reply",
    [httpx2.Response(500, json={"status": "ok"}), httpx2.Response(200, json={"status": "loading"})],
)
def test_probe_ml_down_on_bad_reply(reply: httpx2.Response) -> None:
    transport = httpx2.MockTransport(lambda _req: reply)

    async def go() -> ProbeStatus:
        async with _ml_client(transport) as http:
            return await probe_ml(http, "http://ml:8001", timeout=1)

    assert asyncio.run(go()) == ProbeStatus.DOWN


def test_probe_ml_down_on_timeout() -> None:
    async def slow(_req: httpx2.Request) -> httpx2.Response:
        await asyncio.sleep(5)
        return httpx2.Response(200, json={"status": "ok"})

    async def go() -> ProbeStatus:
        async with _ml_client(httpx2.MockTransport(slow)) as http:
            return await probe_ml(http, "http://ml:8001", timeout=0.05)

    assert asyncio.run(go()) == ProbeStatus.DOWN


def test_probe_db_down_when_unreachable() -> None:
    async def go() -> ProbeStatus:
        # Port 1 on loopback refuses immediately; no network is involved.
        engine = create_async_engine("postgresql+psycopg://sanad:sanad@127.0.0.1:1/sanad")
        try:
            return await probe_db(engine, timeout=2)
        finally:
            await engine.dispose()

    assert asyncio.run(go()) == ProbeStatus.DOWN
