"""A deterministic stand-in for the ONNX engine (the dev image carries no weights)."""

from collections.abc import Sequence

import numpy as np

from sanad_ml.engine import FloatArray


class FakeEngine:
    embed_model = "fake/embed@test"
    rerank_model = "fake/rerank@test"
    dim = 4

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, texts: Sequence[str]) -> FloatArray:
        self.calls.append("embed")
        rows = [[float(len(t)), 1.0, 0.0, 0.0] for t in texts]
        vectors = np.asarray(rows, dtype=np.float32).reshape(len(texts), self.dim)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return np.asarray(vectors / np.maximum(norms, 1e-12), dtype=np.float32)

    def rerank(self, query: str, passages: Sequence[str]) -> list[float]:
        self.calls.append("rerank")
        words = set(query.split())
        return [len(words & set(p.split())) / max(1, len(words)) for p in passages]

    def count_tokens(self, texts: Sequence[str]) -> list[int]:
        self.calls.append("tokenize")
        return [len(t.split()) for t in texts]
