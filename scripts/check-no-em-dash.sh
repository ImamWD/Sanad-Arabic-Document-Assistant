#!/bin/sh
# Owner rule (CLAUDE.md non-negotiable 9): no em dash in code comments, UI text or the README.
# Scans source, UI and config files, tracked and untracked (ignored files are skipped).
# Document content (seed/sources, rendered documents) and backend test data that reproduces
# real documents are out of scope.
set -eu
cd "$(dirname "$0")/.."

if git grep --untracked -n -I "—" -- \
  backend/sanad ml/sanad_ml scripts seed/render.py \
  frontend/src frontend/e2e frontend/index.html \
  Makefile 'docker-compose*.yml' .env.example README.md deploy .github \
  backend/Dockerfile ml/Dockerfile frontend/Dockerfile tools/render/Dockerfile \
  ':!scripts/check-no-em-dash.sh'; then
  echo "error: em dash found (see lines above). Use a period, comma, colon or parentheses." >&2
  exit 1
fi
echo "ok   no em dashes in code, UI text or README"
