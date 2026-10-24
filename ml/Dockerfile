# Sanad ml image (bge-m3 embeddings, bge-reranker-v2-m3 rerank, bge-m3 token counts).
#   models:  build-time only. Downloads the pinned BAAI weights, exports them to ONNX and
#            quantises them to int8 (ml/build/export_models.py). Runs on the BUILD machine's
#            architecture: the ONNX files are plain data, identical for amd64 and arm64, so
#            torch never runs under emulation in a cross-build.
#   runtime: onnxruntime + tokenizers + the baked int8 models, non-root, hub offline.
#   dev:     runtime deps + dev tools, no weights (tests use a fake engine and a tiny
#            generated ONNX graph). The repo is bind-mounted at /app.

ARG PYTHON_IMAGE=python:3.12.15-slim-trixie
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.5

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/ml \
    PATH=/opt/venv/bin:$PATH \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
WORKDIR /app/ml
COPY pyproject.toml uv.lock ./

# --- models (build machine's platform) --------------------------------------------------------
FROM --platform=$BUILDPLATFORM ${PYTHON_IMAGE} AS models
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/export-venv/bin:$PATH \
    UV_PROJECT_ENVIRONMENT=/opt/export-venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    HF_HOME=/hf-cache \
    HF_HUB_DISABLE_TELEMETRY=1
WORKDIR /export
COPY pyproject.toml uv.lock ./
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-default-groups --only-group export
COPY build/export_models.py ./
# The Hugging Face download cache survives rebuilds (a BuildKit cache mount, never in a layer).
RUN --mount=type=cache,target=/hf-cache \
    python export_models.py /opt/models

# --- runtime ------------------------------------------------------------------------------------
FROM base AS runtime
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY --from=models /opt/models /opt/models
COPY sanad_ml ./sanad_ml
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin sanad
USER sanad
ENV ML_MODELS_DIR=/opt/models
EXPOSE 8001
CMD ["uvicorn", "sanad_ml.main:app", "--host", "0.0.0.0", "--port", "8001"]

# --- dev ----------------------------------------------------------------------------------------
FROM base AS dev
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project
