# Sanad ml image (embeddings + rerank).
#   runtime: dependencies + baked source, non-root. Used by docker-compose.yml.
#   dev:     runtime deps + dev tools. The repo is bind-mounted at /app.
# M0 is a health stub. B3 bakes model weights into the runtime stage at build time;
# at runtime the Hugging Face hub is always offline.

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

FROM base AS runtime
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY sanad_ml ./sanad_ml
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin sanad
USER sanad
EXPOSE 8001
CMD ["uvicorn", "sanad_ml.main:app", "--host", "0.0.0.0", "--port", "8001"]

FROM base AS dev
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project
