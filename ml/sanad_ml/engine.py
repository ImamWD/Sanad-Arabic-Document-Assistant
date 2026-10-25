"""Inference on int8 ONNX exports of bge-m3 (embeddings) and bge-reranker-v2-m3 (rerank).

The graphs are produced at image build time by `ml/build/export_models.py`:
- embedder: (input_ids, attention_mask) -> `embedding` [batch, 1024], the CLS vector
- reranker: (input_ids, attention_mask) -> `logit` [batch], one relevance logit per pair

Only onnxruntime, tokenizers and numpy run here, so the service holds neither torch nor
transformers in memory. Everything is CPU-only.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import numpy.typing as npt
import onnxruntime as ort
from tokenizers import Encoding, Tokenizer

FloatArray = npt.NDArray[np.float32]

# onnxruntime ships a telemetry client. The ml container has no route out anyway (internal
# network), but nothing here should even try: no document content leaves the server.
ort.disable_telemetry_events()


class Engine(Protocol):
    """What the HTTP layer needs. Tests swap in a fake."""

    embed_model: str
    rerank_model: str
    dim: int

    def embed(self, texts: Sequence[str]) -> FloatArray: ...

    def rerank(self, query: str, passages: Sequence[str]) -> list[float]: ...

    def count_tokens(self, texts: Sequence[str]) -> list[int]: ...


@dataclass(frozen=True)
class EngineConfig:
    models_dir: Path
    # One text per inference run. Activations are quantised with one scale per tensor, so in a
    # padded batch a text's vector (or score) would depend on the other texts in the batch.
    # It is also the fastest on CPU: 30 rerank candidates of ~300 tokens took 7.7 s one at a
    # time, 10.3 s in batches of 4 and 18.5 s in batches of 8 (padding and attention cost).
    batch_size: int = 1
    embed_max_tokens: int = 1024
    rerank_max_tokens: int = 1024
    # Measured on a 10-CPU Docker VM: 4 threads embed a 350-token text in 0.5 s, all 10 take
    # 1.4 s (core contention). 4 also leaves CPU for the LLM. 0 lets onnxruntime decide.
    threads: int = 4
    mem_arena: bool = False  # off: lower resident memory between requests, slightly slower


@dataclass(frozen=True)
class ModelInfo:
    """`model.json`, written next to each graph by the export script."""

    name: str  # Hugging Face repo id, e.g. "BAAI/bge-m3"
    revision: str  # pinned commit
    variant: str  # e.g. "onnx-int8"
    output: str  # graph output name
    dim: int | None = None

    @property
    def label(self) -> str:
        """Stored with every vector (chunks.embedding_model) to detect stale embeddings."""
        return f"{self.name}@{self.variant}"


def load_model_info(model_dir: Path) -> ModelInfo:
    raw = json.loads((model_dir / "model.json").read_text(encoding="utf-8"))
    return ModelInfo(
        name=raw["name"],
        revision=raw["revision"],
        variant=raw["variant"],
        output=raw["output"],
        dim=raw.get("dim"),
    )


def _session(path: Path, config: EngineConfig) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.enable_cpu_mem_arena = config.mem_arena
    # Pre-packing keeps a second, re-laid-out copy of the int8 weights: ~160 MiB more for
    # both models, and no measurable speed gain here.
    options.add_session_config_entry("session.disable_prepacking", "1")
    if config.threads > 0:
        options.intra_op_num_threads = config.threads
    options.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])


def _tokenizer(path: Path, max_tokens: int | None) -> Tokenizer:
    tokenizer = Tokenizer.from_file(str(path))
    if max_tokens is None:
        tokenizer.no_truncation()
    else:
        tokenizer.enable_truncation(max_length=max_tokens)
    tokenizer.no_padding()
    return tokenizer


def _encode_truncated(tokenizer: Tokenizer, texts: list[str], max_tokens: int) -> list[Encoding]:
    """Encode single texts with the tokenizer's own special tokens, cut to `max_tokens`.

    Truncation happens here rather than in the tokenizer, so the same tokenizer object can
    also count tokens without a cap (each one holds ~280 MiB of vocabulary).
    """
    room = max_tokens - tokenizer.num_special_tokens_to_add(False)
    encodings = []
    for encoding in tokenizer.encode_batch(texts, add_special_tokens=False):
        if len(encoding.ids) > room:
            encoding.truncate(room)
        encodings.append(tokenizer.post_process(encoding))
    return encodings


def _batches(lengths: Sequence[int], size: int) -> list[list[int]]:
    """Indices grouped into batches of similar length, so padding stays small."""
    order = sorted(range(len(lengths)), key=lambda i: lengths[i])
    return [order[i : i + size] for i in range(0, len(order), size)]


def _pad(encodings: Sequence[Encoding], pad_id: int) -> dict[str, npt.NDArray[np.int64]]:
    width = max(len(e.ids) for e in encodings)
    ids = np.full((len(encodings), width), pad_id, dtype=np.int64)
    mask = np.zeros((len(encodings), width), dtype=np.int64)
    for row, encoding in enumerate(encodings):
        ids[row, : len(encoding.ids)] = encoding.ids
        mask[row, : len(encoding.ids)] = 1
    return {"input_ids": ids, "attention_mask": mask}


def _run_batched(
    encodings: Sequence[Encoding],
    batch_size: int,
    pad_id: int,
    run: Callable[[dict[str, npt.NDArray[np.int64]]], npt.NDArray[np.float32]],
) -> list[npt.NDArray[np.float32]]:
    """Run `run` over length-sorted batches and return one result row per input, in order."""
    results: list[npt.NDArray[np.float32] | None] = [None] * len(encodings)
    for batch in _batches([len(e.ids) for e in encodings], batch_size):
        output = run(_pad([encodings[i] for i in batch], pad_id))
        for row, index in enumerate(batch):
            results[index] = output[row]
    return [r for r in results if r is not None]


def _sigmoid(x: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
    return np.asarray(1.0 / (1.0 + np.exp(-x.astype(np.float64))), dtype=np.float32)


class OnnxEngine:
    """bge-m3 embeddings and bge-reranker-v2-m3 scores from int8 ONNX graphs."""

    def __init__(self, config: EngineConfig) -> None:
        self._config = config
        embed_dir = config.models_dir / "embed"
        rerank_dir = config.models_dir / "rerank"
        self._embed_info = load_model_info(embed_dir)
        self._rerank_info = load_model_info(rerank_dir)
        self._embed_session = _session(embed_dir / "model.onnx", config)
        self._rerank_session = _session(rerank_dir / "model.onnx", config)
        # bge-m3's tokenizer both counts tokens for the chunker (uncapped) and feeds the
        # embedder (capped per call). The reranker keeps its own: its whitespace normaliser
        # differs, and a tokenizer must match the model it feeds.
        self._embed_tokenizer = _tokenizer(embed_dir / "tokenizer.json", None)
        self._rerank_tokenizer = _tokenizer(rerank_dir / "tokenizer.json", config.rerank_max_tokens)
        self.embed_model = self._embed_info.label
        self.rerank_model = self._rerank_info.label
        self.dim = self._embed_info.dim or 0

    @staticmethod
    def _pad_id(tokenizer: Tokenizer) -> int:
        pad = tokenizer.token_to_id("<pad>")
        return 0 if pad is None else pad

    def embed(self, texts: Sequence[str]) -> FloatArray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        encodings = _encode_truncated(
            self._embed_tokenizer, list(texts), self._config.embed_max_tokens
        )
        output = self._embed_info.output

        def run(feed: dict[str, npt.NDArray[np.int64]]) -> FloatArray:
            return np.asarray(self._embed_session.run([output], feed)[0], dtype=np.float32)

        rows = _run_batched(
            encodings, self._config.batch_size, self._pad_id(self._embed_tokenizer), run
        )
        vectors = np.stack(rows)
        # bge-m3 dense vectors are L2-normalised CLS states, so cosine = dot product.
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return np.asarray(vectors / np.maximum(norms, 1e-12), dtype=np.float32)

    def rerank(self, query: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        encodings = self._rerank_tokenizer.encode_batch([(query, p) for p in passages])
        output = self._rerank_info.output

        def run(feed: dict[str, npt.NDArray[np.int64]]) -> FloatArray:
            logits = np.asarray(self._rerank_session.run([output], feed)[0], dtype=np.float32)
            return logits.reshape(len(feed["input_ids"]), -1)[:, :1]

        rows = _run_batched(
            encodings, self._config.batch_size, self._pad_id(self._rerank_tokenizer), run
        )
        # Sigmoid of the logit: a 0..1 relevance score, the scale the refusal gate is tuned on.
        return [float(s) for s in _sigmoid(np.concatenate(rows))]

    def count_tokens(self, texts: Sequence[str]) -> list[int]:
        encodings = self._embed_tokenizer.encode_batch(list(texts), add_special_tokens=False)
        return [len(e.ids) for e in encodings]
