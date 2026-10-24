# Sanad render tools image (compose service `render`, profile `tools`).
# Renders Arabic HTML/Markdown to PDF and DOCX with real shaping engines (Chromium/HarfBuzz,
# LibreOffice), and carries the PDF utilities C1b needs for checks and failure fixtures.
# Runs with network_mode: none. Never used at runtime by the app.
#
# Reproducibility: the base image is pinned by date, and apt reads the Debian snapshot archive
# for that same date, so every package version is fixed too.

ARG DEBIAN_IMAGE=debian:trixie-20261020-slim
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

COPY html2pdf /usr/local/bin/html2pdf
