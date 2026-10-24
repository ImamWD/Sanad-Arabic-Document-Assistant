"""ml service: embeddings, rerank scores and token counts for api and worker.

Endpoints (internal network only, called by api and worker):
- POST /embed     {"texts": [...]}                -> 1024-d L2-normalised bge-m3 vectors
- POST /rerank    {"query": "...", "passages": [...]} -> 0..1 scores, in input order
- POST /tokenize  {"texts": [...]}                -> bge-m3 token counts, no special tokens
- GET  /health    ok once both models are loaded

Weights are baked into the image at build time (ml/Dockerfile) and the Hugging Face hub is
offline at runtime. No request text is logged.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal, TypeVar

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, StringConstraints

from sanad_ml.engine import Engine, EngineConfig, OnnxEngine

# Request limits: generous for the worker's batches, small enough that one request can't
# exhaust memory. A chunk is at most 512 tokens (~4,000 characters of Arabic).
MAX_TEXTS = 256
MAX_CHARS = 20_000

Text = Annotated[str, StringConstraints(max_length=MAX_CHARS)]
T = TypeVar("T")


class Health(BaseModel):
    status: Literal["ok"]
    embed_model: str | None = None
    rerank_model: str | None = None


class TextsRequest(BaseModel):
    texts: list[Text] = Field(max_length=MAX_TEXTS)


class EmbedResponse(BaseModel):
    model: str
    dim: int
    embeddings: list[list[float]]


class RerankRequest(BaseModel):
    query: Text
    passages: list[Text] = Field(max_length=MAX_TEXTS)


class RerankResponse(BaseModel):
    model: str
    scores: list[float]


class TokenizeResponse(BaseModel):
    model: str
    counts: list[int]


def config_from_env() -> EngineConfig:
    return EngineConfig(
        models_dir=Path(os.environ.get("ML_MODELS_DIR", "/opt/models")),
        batch_size=int(os.environ.get("ML_BATCH_SIZE", "8")),
        embed_max_tokens=int(os.environ.get("ML_EMBED_MAX_TOKENS", "1024")),
        rerank_max_tokens=int(os.environ.get("ML_RERANK_MAX_TOKENS", "1024")),
        threads=int(os.environ.get("ML_THREADS", "0")),
        mem_arena=os.environ.get("ML_MEM_ARENA", "0") == "1",
    )


def max_concurrency_from_env() -> int:
    return max(1, int(os.environ.get("ML_MAX_CONCURRENCY", "1")))


def create_app(load_engine: Callable[[], Engine], max_concurrency: int = 1) -> FastAPI:
    # One inference at a time by default: onnxruntime already uses every core for one batch,
    # and each concurrent batch would add its own activation memory.
    gate = asyncio.Semaphore(max_concurrency)

    async def infer(fn: Callable[[], T]) -> T:
        async with gate:
            return await run_in_threadpool(fn)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Loading takes a few seconds; uvicorn serves nothing (health included) until done.
        app.state.engine = load_engine()
        yield

    app = FastAPI(
        title="Sanad ML", version="0.2.0", docs_url=None, redoc_url=None, lifespan=lifespan
    )

    def engine(request: Request) -> Engine:
        loaded: Engine = request.app.state.engine
        return loaded

    @app.get("/health")
    async def health(request: Request) -> Health:
        loaded = engine(request)
        return Health(
            status="ok", embed_model=loaded.embed_model, rerank_model=loaded.rerank_model
        )

    # Inference is CPU-bound and releases the GIL inside onnxruntime: run it off the loop.
    @app.post("/embed")
    async def embed(body: TextsRequest, request: Request) -> EmbedResponse:
        loaded = engine(request)
        vectors = await infer(lambda: loaded.embed(body.texts))
        return EmbedResponse(model=loaded.embed_model, dim=loaded.dim, embeddings=vectors.tolist())

    @app.post("/rerank")
    async def rerank(body: RerankRequest, request: Request) -> RerankResponse:
        loaded = engine(request)
        scores = await infer(lambda: loaded.rerank(body.query, body.passages))
        return RerankResponse(model=loaded.rerank_model, scores=scores)

    @app.post("/tokenize")
    async def tokenize(body: TextsRequest, request: Request) -> TokenizeResponse:
        loaded = engine(request)
        # Tokenizing is fast and never waits behind a long embedding batch.
        counts = await run_in_threadpool(loaded.count_tokens, body.texts)
        return TokenizeResponse(model=loaded.embed_model, counts=counts)

    return app


def _load_default() -> Engine:
    return OnnxEngine(config_from_env())


app = create_app(_load_default, max_concurrency_from_env())
