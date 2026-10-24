#!/bin/sh
# node_modules lives in a docker volume. Reinstall it whenever package-lock.json has changed
# since the last install, so the volume never goes stale silently.
set -eu
stamp=node_modules/.sanad-lock.sha256
want=$(sha256sum package-lock.json | cut -d' ' -f1)
if [ "$(cat "$stamp" 2>/dev/null || true)" != "$want" ]; then
  echo "package-lock.json changed: running npm ci" >&2
  npm ci --no-audit --no-fund
  echo "$want" > "$stamp"
fi
