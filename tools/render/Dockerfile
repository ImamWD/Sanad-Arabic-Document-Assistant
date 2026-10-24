# Sanad render tools image (compose service `render`, profile `tools`).
# Renders Arabic HTML/Markdown to PDF and DOCX with real shaping engines (Chromium/HarfBuzz,
# LibreOffice), and carries the PDF utilities C1b needs for checks and failure fixtures.
# Runs with network_mode: none. Never used at runtime by the app.
#
# Reproducibility: the base image is pinned by date, and apt reads the Debian snapshot archive
# for that same date, so every package version is fixed too.

ARG DEBIAN_IMAGE=debian:trixie-20261020-slim
# The uv release backend/Dockerfile uses; only mounted to install pypdfium2 below.
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.5

FROM ${UV_IMAGE} AS uv

FROM ${DEBIAN_IMAGE}

ARG DEBIAN_SNAPSHOT=20261020T000000Z
RUN sed -i \
      -e "s|http://deb.debian.org/debian-security|http://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}|" \
      -e "s|http://deb.debian.org/debian|http://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}|" \
      /etc/apt/sources.list.d/debian.sources \
 && apt-get -o Acquire::Check-Valid-Until=false -o Acquire::Retries=5 update \
 && DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=5 install -y --no-install-recommends \
      chromium \
      libreoffice-writer-nogui \
      pandoc \
      poppler-utils \
      qpdf \
      img2pdf \
      python3 \
      python3-yaml \
      python3-markdown \
      python3-docx \
      fontconfig \
      fonts-noto-core \
      fonts-hosny-amiri \
      fonts-kacst-one \
      fonts-dejavu-core \
      fonts-liberation \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && fc-cache -f \
 && dpkg-query -W -f='${Package}=${Version}\n' > /usr/share/sanad-render-packages.txt

# Chromium and LibreOffice both want a writable profile directory.
ENV HOME=/tmp \
    LANG=C.UTF-8

# pypdfium2 for scripts/check_eval.py (C1b). Debian doesn't package it. Same version as
# backend/uv.lock, installed only from wheels with these hashes (manylinux aarch64, x86_64).
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    printf '%s\n' 'pypdfium2==5.14.0 \
      --hash=sha256:f1b696e6901e16f114a2ec6332e5e3f8f5033a901614ead28499ab18ca6024f5 \
      --hash=sha256:11f281613fa22313d9c7ab89947665e84eccf8ebe40e1198a84a88352305648d' \
      > /tmp/requirements.txt \
 && UV_PYTHON_DOWNLOADS=never UV_HTTP_TIMEOUT=300 uv pip install --python /usr/bin/python3 --system \
      --break-system-packages --require-hashes --no-deps --only-binary :all: \
      -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt \
 && python3 -c 'import pypdfium2; pypdfium2.PdfDocument.new().close()'

COPY html2pdf /usr/local/bin/html2pdf
