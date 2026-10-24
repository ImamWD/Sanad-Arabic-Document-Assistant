# Sanad backend image, shared by the `api` and `worker` services.
#   runtime: dependencies + baked source, non-root. Used by docker-compose.yml.
#   dev:     runtime deps + dev tools (ruff, mypy, pytest). The repo is bind-mounted at /app.
# Paths mirror the repo: the source lives at /app/backend/sanad, so a bind mount of the repo
# at /app simply replaces the baked copy.

ARG PYTHON_IMAGE=python:3.12.15-slim-trixie
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.5

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    PATH=/opt/venv/bin:$PATH \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
WORKDIR /app/backend
COPY pyproject.toml uv.lock ./

FROM base AS runtime
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY sanad ./sanad
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin sanad
USER sanad
EXPOSE 8000
CMD ["uvicorn", "sanad.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS dev
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project
