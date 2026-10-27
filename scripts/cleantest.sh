#!/usr/bin/env bash
# Clean-machine test (ROADMAP H2). Clones Sanad into a temporary directory, starts it as its
# own compose project with no .env (demo mode), and times it until the guest gets a real answer
# with a citation, driven through the API the way the smoke test drives the UI. Along the way it
# samples memory, times the model download into a fresh model volume, probes egress from the
# content containers, and tears everything down. It prints a summary for the README.
#
#   scripts/cleantest.sh [--repo URL] [--ref REF] [--port N] [--no-cache] [--keep]
#
#   --repo URL   what to clone (default: the public GitHub repository)
#   --ref REF    branch or tag to test (default: main)
#   --port N     host port for the web UI (default: 8080; must be free)
#   --no-cache   rebuild every image layer (re-downloads Python/npm packages and the ml model
#                weights; base images already on this machine are reused either way)
#   --keep       leave the stack, clone and images in place afterwards (tear down by hand)
#   --preflight-only
#                check prerequisites, clone and report what is already cached, then stop
#                without starting anything
#
# Needs bash, git and Docker with Compose v2. Works on Linux (x86_64, arm64) and macOS.
# It only ever touches the compose project `sanad-cleantest`, images tagged `:sanad-cleantest`
# and the volume `sanad-cleantest-ollama-models`; other Sanad stacks and volumes are left alone.
set -euo pipefail

PROJECT=sanad-cleantest
REPO=https://github.com/ImamWD/Sanad-Arabic-Document-Assistant.git
REF=main
PORT=8080
NO_CACHE=
KEEP=
PREFLIGHT_ONLY=
# Dev set D08 (eval/dev_questions.yaml), the smoke test's question; the README demo uses it too.
QUESTION='While schools were shut in 2020, roughly how many girls kept up their studies by following the radio broadcasts?'
SAMPLE_SECONDS=3
INDEX_TIMEOUT_SECONDS=2700
ANSWER_TIMEOUT_SECONDS=900

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO=$2; shift 2 ;;
    --ref) REF=$2; shift 2 ;;
    --port) PORT=$2; shift 2 ;;
    --no-cache) NO_CACHE=1; shift ;;
    --keep) KEEP=1; shift ;;
    --preflight-only) PREFLIGHT_ONLY=1; shift ;;
    -h | --help) sed -n '2,23p' "$0"; exit 0 ;;
    *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
done

# Every compose command below runs with these, teardown included: the project name, the image
# tag, and a model volume of our own (never the shared sanad-ollama-models). No .env is read
# from the clone, and these override anything exported in this shell.
export COMPOSE_PROJECT_NAME=$PROJECT
export SANAD_INSTANCE=$PROJECT
export OLLAMA_MODELS_VOLUME=$PROJECT-ollama-models
export WEB_PORT=$PORT
unset COMPOSE_FILE COMPOSE_PROFILES SANAD_ENV 2>/dev/null || true

TMP_ROOT=${TMPDIR:-/tmp}
OUT=$(mktemp -d "${TMP_ROOT%/}/sanad-cleantest.XXXXXX")
CLONE=$OUT/repo
EVENTS=$OUT/events.log
MEMLOG=$OUT/memory.tsv
SUMMARY=$OUT/summary.txt
: >"$EVENTS"
: >"$MEMLOG"

now() { date +%s; }
log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*" | tee -a "$EVENTS" >&2; }
die() { log "FAILED: $*"; exit 1; }
compose() { docker compose -p "$PROJECT" --project-directory "$CLONE" "$@"; }
secs() { printf '%ss' "$1"; }
mmss() { printf '%dm %02ds' $(($1 / 60)) $(($1 % 60)); }

# RFC 3339 (docker inspect) to epoch seconds, with GNU date (Linux) or BSD date (macOS).
epoch() {
  local ts=${1%%.*}
  ts=${ts%Z}
  date -u -d "${ts}Z" +%s 2>/dev/null || date -u -j -f '%Y-%m-%dT%H:%M:%S' "$ts" +%s
}

SAMPLER_PID=
STACK_STARTED=
teardown() {
  local status=$?
  if [ -n "$SAMPLER_PID" ]; then kill "$SAMPLER_PID" 2>/dev/null || true; fi
  if [ "$status" -ne 0 ] && [ -n "$STACK_STARTED" ]; then
    compose logs --no-color --tail=200 >"$OUT/compose-logs.txt" 2>&1 || true
    log "compose logs saved to $OUT/compose-logs.txt"
  fi
  if [ -n "$KEEP" ]; then
    log "--keep: left running. Tear down with:"
    log "  COMPOSE_PROJECT_NAME=$PROJECT SANAD_INSTANCE=$PROJECT OLLAMA_MODELS_VOLUME=$OLLAMA_MODELS_VOLUME docker compose --project-directory $CLONE down -v"
  else
    if [ -n "$STACK_STARTED" ]; then
      log "tearing down $PROJECT (its own volumes only)"
      compose --profile tools down -v --remove-orphans >/dev/null 2>&1 || true
      docker volume rm "$OLLAMA_MODELS_VOLUME" >/dev/null 2>&1 || true
      for image in sanad-backend sanad-ml sanad-web; do
        docker image rm "$image:$PROJECT" >/dev/null 2>&1 || true
      done
    fi
    rm -rf "$CLONE"
  fi
  log "logs and summary kept in $OUT"
  exit "$status"
}
trap teardown EXIT
trap 'exit 130' INT TERM

# --- preflight -------------------------------------------------------------------------------
command -v git >/dev/null || die "git is not installed"
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 (docker compose) is needed"
if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
  die "port $PORT is in use; free it or pass --port"
fi
if [ -n "$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" \
  --filter "label=com.docker.compose.container-number")" ]; then
  die "a $PROJECT project already exists; remove it first (it is this script's own project)"
fi
if docker volume inspect "$OLLAMA_MODELS_VOLUME" >/dev/null 2>&1; then
  log "removing the leftover $OLLAMA_MODELS_VOLUME from an earlier clean test"
  docker volume rm "$OLLAMA_MODELS_VOLUME" >/dev/null
fi

MACHINE=$(docker info --format '{{.OSType}}/{{.Architecture}}, {{.NCPU}} CPUs, {{.MemTotal}} bytes for Docker, Docker {{.ServerVersion}}')
DOCKER_MEM=$(docker info --format '{{.MemTotal}}')
MACHINE=${MACHINE/$DOCKER_MEM bytes/$(awk -v b="$DOCKER_MEM" 'BEGIN { printf "%.1f GiB", b / 1073741824 }')}
COMPOSE_VERSION=$(docker compose version --short)
log "machine: $MACHINE, Compose $COMPOSE_VERSION"
log "output: $OUT"

# --- clone -----------------------------------------------------------------------------------
T_CLONE=$(now)
log "cloning $REPO ($REF)"
git clone --quiet --depth 1 --branch "$REF" "$REPO" "$CLONE" || die "git clone failed"
COMMIT=$(git -C "$CLONE" rev-parse --short HEAD)
[ ! -e "$CLONE/.env" ] || die "the clone has a .env; a clean test runs without one"
D_CLONE=$(($(now) - T_CLONE))
log "commit $COMMIT, cloned in $(secs "$D_CLONE")"

# What this machine already had: base images and the build cache cannot be made truly cold here
# without deleting what other stacks use, so the summary says what was reused.
IMAGES=$(compose config --images 2>/dev/null | sort -u)
CACHED=0
TOTAL_IMAGES=0
MISSING_LIST=
for image in $IMAGES; do
  case "$image" in *":$PROJECT") continue ;; esac  # built by this run
  TOTAL_IMAGES=$((TOTAL_IMAGES + 1))
  if docker image inspect "$image" >/dev/null 2>&1; then
    CACHED=$((CACHED + 1))
  else
    MISSING_LIST="$MISSING_LIST $image"
  fi
done
BUILD_CACHE=$(docker system df --format '{{.Type}}\t{{.Size}}' 2>/dev/null | awk -F'\t' '$1 == "Build Cache" { print $2 }')
log "already on this machine: $CACHED of $TOTAL_IMAGES pulled images; build cache ${BUILD_CACHE:-unknown}"
if [ -n "$PREFLIGHT_ONLY" ]; then
  [ -z "$MISSING_LIST" ] || log "would pull:$MISSING_LIST"
  log "preflight passed; nothing was started"
  exit 0
fi

# --- memory sampler --------------------------------------------------------------------------
# Every few seconds: each running container of the project and its memory, in MiB. Images that
# compose builds carry the project label too, so the guest and probe containers this script
# starts from them would match it; only compose's own containers have a container-number.
sample_memory() {
  while :; do
    ids=$(docker ps -q --filter "label=com.docker.compose.project=$PROJECT" \
      --filter "label=com.docker.compose.container-number")
    if [ -n "$ids" ]; then
      t=$(date +%s)
      # shellcheck disable=SC2086
      docker stats --no-stream --format '{{.Name}}|{{.MemUsage}}' $ids 2>/dev/null | awk -F'|' -v t="$t" '
        function mib(s,   n, u) {
          n = s; sub(/[A-Za-z]+$/, "", n)
          u = s; sub(/^[0-9.]+/, "", u)
          if (u == "B") return n / 1048576
          if (u == "KiB" || u == "kB") return n / 1024
          if (u == "GiB" || u == "GB") return n * 1024
          if (u == "TiB" || u == "TB") return n * 1048576
          return n
        }
        { split($2, used, " / "); printf "%s\t%s\t%.1f\n", t, $1, mib(used[1]) }' >>"$MEMLOG" || true
    fi
    sleep "$SAMPLE_SECONDS"
  done
}
sample_memory &
SAMPLER_PID=$!

# --- start -----------------------------------------------------------------------------------
T0=$(now)
STACK_STARTED=1
log "pulling images"
compose pull --quiet --ignore-buildable >"$OUT/pull.log" 2>&1 || die "pull failed (see $OUT/pull.log)"
T_PULLED=$(now)
log "building images${NO_CACHE:+ (no cache)}"
compose build ${NO_CACHE:+--no-cache} >"$OUT/build.log" 2>&1 || die "build failed (see $OUT/build.log)"
T_BUILT=$(now)
log "starting the stack and waiting until healthy (this includes the model download)"
compose up -d --wait >"$OUT/up.log" 2>&1 || die "up failed (see $OUT/up.log)"
T_UP=$(now)
log "healthy after $(mmss $((T_UP - T0)))"

# The model download: ollama-init's own run time, into the fresh model volume.
INIT_ID=$(compose ps -aq ollama-init)
D_MODEL=
if [ -n "$INIT_ID" ]; then
  started=$(docker inspect -f '{{.State.StartedAt}}' "$INIT_ID")
  finished=$(docker inspect -f '{{.State.FinishedAt}}' "$INIT_ID")
  D_MODEL=$(($(epoch "$finished") - $(epoch "$started")))
fi
MODEL_LIST=$(compose exec -T ollama ollama list 2>/dev/null | awk 'NR > 1 { printf "%s%s %s %s", sep, $1, $3, $4; sep = ", " }')
log "model download (ollama-init): $(mmss "${D_MODEL:-0}"); models: ${MODEL_LIST:-unknown}"

# --- the guest, through the API --------------------------------------------------------------
# A small client in the backend image, on the published network, talking to nginx like a
# browser: guest login, wait until the seed corpus is indexed, then ask and check the citation.
# Every line it prints is stamped with this machine's clock as it arrives.
cat >"$OUT/guest.py" <<'PY'
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "http://web:8080/api"
QUESTION = os.environ["QUESTION"]
INDEX_TIMEOUT = int(os.environ["INDEX_TIMEOUT"])
ANSWER_TIMEOUT = int(os.environ["ANSWER_TIMEOUT"])
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def say(*words: object) -> None:
    print(*words, flush=True)


def call(method: str, path: str, body: object = None, timeout: float = 60) -> object:
    data = json.dumps(body if body is not None else {}).encode() if method == "POST" else None
    request = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "X-Sanad": "1", "Accept": "application/json"},
    )
    with opener.open(request, timeout=timeout) as response:
        return json.load(response)


me = call("POST", "/auth/guest")
say("GUEST", me.get("email"))

deadline = time.time() + INDEX_TIMEOUT
last = None
while True:
    docs = call("GET", "/documents?page_size=100")
    states = [item["status"] for item in docs["items"]]
    ready, failed = states.count("ready"), states.count("failed")
    progress = (ready, failed, len(states))
    if progress != last:
        say("INDEX", ready, failed, len(states))
        last = progress
    if states and ready + failed == len(states):
        break
    if time.time() > deadline:
        say("ERROR", "the seed corpus was not indexed in time")
        sys.exit(1)
    time.sleep(5)

for attempt in range(1, 6):
    started = time.time()
    try:
        result = call("POST", "/ask", {"question": QUESTION}, timeout=ANSWER_TIMEOUT)
    except urllib.error.HTTPError as err:
        say("RETRY", attempt, "HTTP", err.code, err.read().decode()[:200])
        time.sleep(15)
        continue
    took = round(time.time() - started, 1)
    citations = result.get("citations") or []
    first = citations[0] if citations else {}
    say(
        "ANSWER",
        result.get("outcome"),
        len(citations),
        took,
        json.dumps({"title": first.get("title"), "page": first.get("page_number")}, ensure_ascii=False),
    )
    ok = result.get("outcome") in ("answered", "low_confidence") and citations
    sys.exit(0 if ok else 3)
say("ERROR", "no answer after 5 attempts")
sys.exit(1)
PY

log "guest: login, wait for the seed corpus, ask: \"$QUESTION\""
GUEST_STATUS=0
docker run --rm -i --network "${PROJECT}_edge" \
  -e QUESTION="$QUESTION" -e INDEX_TIMEOUT="$INDEX_TIMEOUT_SECONDS" -e ANSWER_TIMEOUT="$ANSWER_TIMEOUT_SECONDS" \
  --entrypoint python "sanad-backend:$PROJECT" - <"$OUT/guest.py" |
  while IFS= read -r line; do
    printf '%s %s\n' "$(now)" "$line" >>"$OUT/guest.log"
    log "guest: $line"
  done || GUEST_STATUS=$?
[ "$GUEST_STATUS" -eq 0 ] || die "the guest did not get an answer with a citation (see $OUT/guest.log)"

T_INDEXED=$(awk '$2 == "INDEX" { t = $1 } END { print t }' "$OUT/guest.log")
INDEX_LAST=$(awk '$2 == "INDEX" { r = $3; f = $4; n = $5 } END { print r " ready, " f " failed, of " n }' "$OUT/guest.log")
T_ANSWER=$(awk '$2 == "ANSWER" { print $1 }' "$OUT/guest.log")
ANSWER_LINE=$(awk '$2 == "ANSWER" { $1 = ""; $2 = ""; sub(/^  /, ""); print }' "$OUT/guest.log")
ANSWER_OUTCOME=$(printf '%s' "$ANSWER_LINE" | awk '{ print $1 }')
ANSWER_CITATIONS=$(printf '%s' "$ANSWER_LINE" | awk '{ print $2 }')
ANSWER_TOOK=$(printf '%s' "$ANSWER_LINE" | awk '{ print $3 }')
ANSWER_FIRST=$(printf '%s' "$ANSWER_LINE" | cut -d' ' -f4-)

# --- egress ----------------------------------------------------------------------------------
# The same probe as the CI egress step (RV4): from the backend image, inside each container's
# own network namespace (ollama and db have no Python). web is on the published network and
# must get out, which proves the probe can see a route when there is one.
PROBE='import socket
for host in ("1.1.1.1", "8.8.8.8", "example.com"):
    try:
        socket.create_connection((host, 443), timeout=5).close()
    except OSError:
        continue
    print("reached " + host)
    break
else:
    print("no route out")'
EGRESS_OK=1
EGRESS_DETAIL=
for service in web api worker ml ollama db; do
  id=$(compose ps -q "$service")
  if [ -z "$id" ]; then
    EGRESS_OK=
    EGRESS_DETAIL="$EGRESS_DETAIL $service=not-running"
    continue
  fi
  result=$(docker run --rm --network "container:$id" --entrypoint python "sanad-backend:$PROJECT" -c "$PROBE" 2>&1 | tail -1)
  log "egress probe: $service: $result"
  EGRESS_DETAIL="$EGRESS_DETAIL $service=\"$result\""
  if [ "$service" = web ]; then
    case "$result" in reached*) ;; *) EGRESS_OK= ;; esac
  elif [ "$result" != "no route out" ]; then
    EGRESS_OK=
  fi
done

# --- memory ----------------------------------------------------------------------------------
kill "$SAMPLER_PID" 2>/dev/null || true
SAMPLER_PID=
PEAK=$(awk -F'\t' '{ sum[$1] += $3 } END { for (t in sum) if (sum[t] > max) { max = sum[t]; at = t } printf "%.0f %s", max, at }' "$MEMLOG")
PEAK_MIB=${PEAK% *}
PEAK_AT=${PEAK#* }
PEAK_TOP=$(awk -F'\t' -v at="$PEAK_AT" '$1 == at { name = $2; sub("^" proj "-", "", name); sub(/-1$/, "", name); printf "%s %.1f\n", name, $3 / 1024 }' proj="$PROJECT" "$MEMLOG" |
  sort -k2 -nr | head -4 | awk '{ printf "%s%s %s GiB", sep, $1, $2; sep = ", " }')
PER_SERVICE=$(awk -F'\t' '{ if ($3 > max[$2]) max[$2] = $3 } END { for (n in max) printf "%s %.0f\n", n, max[n] }' "$MEMLOG" |
  sed "s/^$PROJECT-//; s/-1 / /" | sort -k2 -nr | awk '{ printf "%s%s %s MiB", sep, $1, $2; sep = ", " }')

# --- summary ---------------------------------------------------------------------------------
{
  echo "Sanad clean-machine test, $(date -u '+%Y-%m-%d %H:%M UTC'), commit $COMMIT ($REF)"
  echo "Machine:             $MACHINE, Compose $COMPOSE_VERSION"
  echo "Already cached:      $CACHED of $TOTAL_IMAGES pulled images; build cache ${BUILD_CACHE:-unknown}${NO_CACHE:+; images rebuilt with --no-cache}"
  [ -z "$MISSING_LIST" ] || echo "Pulled in this run:  $MISSING_LIST"
  echo "Clone:               $(mmss "$D_CLONE")"
  echo "Pull images:         $(mmss $((T_PULLED - T0)))"
  echo "Build images:        $(mmss $((T_BUILT - T_PULLED)))"
  echo "Up, healthy:         $(mmss $((T_UP - T_BUILT)))  (model download into a fresh volume: $(mmss "${D_MODEL:-0}"); ${MODEL_LIST:-?})"
  echo "Seed corpus indexed: $(mmss $((T_INDEXED - T0))) after start  ($INDEX_LAST)"
  echo "First answer:        $(mmss $((T_ANSWER - T0))) after start  (the answer took ${ANSWER_TOOK}s; $ANSWER_OUTCOME, $ANSWER_CITATIONS citation(s); first: $ANSWER_FIRST)"
  echo "Peak memory:         $(awk -v m="$PEAK_MIB" 'BEGIN { printf "%.1f GiB", m / 1024 }') across the stack  (at the peak: $PEAK_TOP)"
  echo "Per service peak:    $PER_SERVICE"
  if [ -n "$EGRESS_OK" ]; then
    echo "Egress:              none from api, worker, ml, ollama, db (base compose file); web reached out, so the probe works"
  else
    echo "Egress:              CHECK FAILED:$EGRESS_DETAIL"
  fi
} >"$SUMMARY"

echo
cat "$SUMMARY"
echo
[ -n "$EGRESS_OK" ] || die "egress check failed"
log "clean test passed"
