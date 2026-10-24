#!/bin/sh
# Measure a model's memory inside a Linux container: the number the 8 GB Docker budget needs.
#   sh spikes/s3/container_mem.sh <model> <memory limit, e.g. 7g> <use_mmap true|false> [prompt ids]
# Starts ollama/ollama (same version as the host) with the host's model store mounted read-only,
# runs the prompts through run.py --cpu, then prints the container cgroup's peak, its anonymous
# memory (what can't be reclaimed) and its file cache (mapped GGUF pages, reclaimable).
# Synthetic seed prompts only; the container has no other data. It is removed afterwards.
set -eu
MODEL=$1; LIMIT=$2; MMAP=$3; IDS=${4:-P01,P02,P03}
NAME=s3-ollama-memtest
docker rm -f $NAME >/dev/null 2>&1 || true
docker run -d --name $NAME --memory "$LIMIT" --memory-swap "$LIMIT" -p 127.0.0.1:11500:11434 \
  -v "$HOME/.ollama/models:/root/.ollama/models:ro" -e OLLAMA_NOPRUNE=1 ollama/ollama:0.40.10 >/dev/null
until curl -s http://127.0.0.1:11500/api/version >/dev/null; do sleep 1; done
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T backend-dev \
  python spikes/s3/run.py --model "$MODEL" --cpu --use-mmap "$MMAP" --ids "$IDS" \
  --target http://host.docker.internal:11500 --label "Linux container ($LIMIT, use_mmap=$MMAP)" 2>&1 \
  | grep -E "got=|prompt=|memory|ERROR|WARN" || true
echo "limit=$LIMIT use_mmap=$MMAP oom_killed=$(docker inspect -f '{{.State.OOMKilled}}' $NAME) running=$(docker inspect -f '{{.State.Running}}' $NAME)"
docker exec $NAME sh -c 'echo "peak_bytes $(cat /sys/fs/cgroup/memory.peak)"; echo "current_bytes $(cat /sys/fs/cgroup/memory.current)"; grep -E "^(anon|file|file_mapped|shmem) " /sys/fs/cgroup/memory.stat' 2>/dev/null \
  | awk '{printf "%s %.2f GiB\n", $1, $2/1073741824}'
docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' $NAME
docker rm -f $NAME >/dev/null
