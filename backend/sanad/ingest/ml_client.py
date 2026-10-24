"""The worker's client for the ml service: token counts (chunking) and embeddings (indexing).

Requests are batched to stay under the service's per-request limits. Any transport or
server failure becomes `MlUnavailableError`, which the worker treats as transient.
"""

from collections.abc import Callable, Sequence
from typing import Any, Protocol

import httpx2

TOKENIZE_BATCH = 256  # the ml service accepts at most 256 texts per request


class MlUnavailableError(Exception):
    """The ml service couldn't be reached or answered with an error."""


class MlService(Protocol):
    """What the worker needs from the ml service (tests pass a fake)."""

    def healthy(self) -> bool: ...

    def count_tokens(self, texts: Sequence[str]) -> list[int]: ...

    def embed(
        self, texts: Sequence[str], on_batch: Callable[[], None] = ...
    ) -> tuple[str, list[list[float]]]: ...

    def close(self) -> None: ...


class MlClient:
    def __init__(self, base_url: str, timeout: float, embed_batch: int) -> None:
        self._client = httpx2.Client(base_url=base_url, timeout=timeout)
        self._embed_batch = embed_batch

    def close(self) -> None:
        self._client.close()

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=body)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
        except (httpx2.HTTPError, ValueError) as exc:
            raise MlUnavailableError(f"{path}: {type(exc).__name__}") from exc
        return data

    def healthy(self) -> bool:
        try:
            response = self._client.get("/health", timeout=5)
            return response.status_code == 200 and response.json().get("status") == "ok"
        except (httpx2.HTTPError, ValueError):
            return False

    def count_tokens(self, texts: Sequence[str]) -> list[int]:
        counts: list[int] = []
        for start in range(0, len(texts), TOKENIZE_BATCH):
            batch = list(texts[start : start + TOKENIZE_BATCH])
            counts.extend(self._post("/tokenize", {"texts": batch})["counts"])
        return counts

    def embed(
        self, texts: Sequence[str], on_batch: Callable[[], None] = lambda: None
    ) -> tuple[str, list[list[float]]]:
        """(model label, one vector per text). `on_batch` runs after each batch, so the
        worker can show it is alive during a long document."""
        model = ""
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._embed_batch):
            batch = list(texts[start : start + self._embed_batch])
            data = self._post("/embed", {"texts": batch})
            if len(data["embeddings"]) != len(batch) or (model and data["model"] != model):
                raise MlUnavailableError("/embed: inconsistent response")
            model = str(data["model"])
            vectors.extend(data["embeddings"])
            on_batch()
        return model, vectors
