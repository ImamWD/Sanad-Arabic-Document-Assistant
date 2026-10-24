"""The api's async client for the ml service: embed the question, rerank the candidates.

Contract (B3): `/embed` returns L2-normalised bge-m3 vectors; `/rerank` returns one 0..1
score per passage, in input order. Any failure becomes `MlUnavailableError` (ML_UNAVAILABLE).
"""

from collections.abc import Sequence
from typing import Any, Protocol

import httpx2


class MlUnavailableError(Exception):
    """The ml service couldn't be reached or answered with an error."""


class AskMl(Protocol):
    """What retrieval needs from the ml service (tests pass a fake)."""

    async def embed(self, text: str) -> list[float]: ...

    async def rerank(self, query: str, passages: Sequence[str]) -> list[float]: ...


class AskMlClient:
    def __init__(self, client: httpx2.AsyncClient, base_url: str, timeout: float) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(
                f"{self._base_url}{path}", json=body, timeout=self._timeout
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
        except (httpx2.HTTPError, ValueError) as exc:
            raise MlUnavailableError(f"{path}: {type(exc).__name__}") from exc
        return data

    async def embed(self, text: str) -> list[float]:
        data = await self._post("/embed", {"texts": [text]})
        try:
            vector: list[float] = data["embeddings"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise MlUnavailableError("/embed: unexpected response") from exc
        return vector

    async def rerank(self, query: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        data = await self._post("/rerank", {"query": query, "passages": list(passages)})
        scores = data.get("scores")
        if not isinstance(scores, list) or len(scores) != len(passages):
            raise MlUnavailableError("/rerank: unexpected response")
        return [float(s) for s in scores]
