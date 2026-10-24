# Sanad backend image, shared by the `api` and `worker` services.
#   runtime: dependencies + baked source, non-root. Used by docker-compose.yml.
#   dev:     runtime deps + dev tools (ruff, mypy, pytest). The repo is bind-mounted at /app.
# Paths mirror the repo: the source lives at /app/backend/sanad, so a bind mount of the repo
# at /app simply replaces the baked copy.

ARG PYTHON_IMAGE=python:3.12.15-slim-trixie
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.5

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS base

# LibreOffice (DOCX/TXT -> PDF) and Arabic fonts, for the worker. They sit in `base` so that
# backend-dev, where scripts/check_eval.py runs, converts with the very same soffice and
# fonts as the worker: fonts change line breaks, and line breaks change DOCX page numbers.
# Package set and Debian snapshot date match tools/render/Dockerfile (C1b's checker), so
# every package version is fixed and identical to the renderer's.
ARG DEBIAN_SNAPSHOT=20261020T000000Z
RUN sed -i \
      -e "s|http://deb.debian.org/debian-security|http://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}|" \
      -e "s|http://deb.debian.org/debian|http://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}|" \
      /etc/apt/sources.list.d/debian.sources \
 && apt-get -o Acquire::Check-Valid-Until=false -o Acquire::Retries=5 update \
 && DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=5 install -y --no-install-recommends \
      libreoffice-writer-nogui \
      fontconfig \
      fonts-noto-core \
      fonts-hosny-amiri \
      fonts-kacst-one \
      fonts-dejavu-core \
      fonts-liberation \
 && rm -rf /var/lib/apt/lists/* \
 && fc-cache -f \
 && dpkg-query -W -f='${Package}=${Version}\n' > /usr/share/sanad-backend-packages.txt

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    PATH=/opt/venv/bin:$PATH \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    LANG=C.UTF-8
WORKDIR /app/backend
COPY pyproject.toml uv.lock ./

FROM base AS runtime
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY sanad ./sanad
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin sanad \
 && mkdir -p /data/files \
 && chown sanad /data/files
USER sanad
EXPOSE 8000
CMD ["uvicorn", "sanad.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS dev
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project
