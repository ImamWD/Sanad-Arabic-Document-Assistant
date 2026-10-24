#!/bin/sh
# Host-side (macOS) memory check for S3, run while the model is still loaded after a run.py run:
#   sh spikes/s3/footprint.sh
# phys_footprint counts dirty memory: weights repacked for the CPU, KV cache, compute buffers.
# It leaves out clean mapped file pages, which the OS can drop. That dirty total is what a
# container's memory limit has to hold. RSS overstates it (it includes the mapped GGUF file).
for pid in $(pgrep -f llama-server); do
  echo "llama-server $pid: $(footprint -p "$pid" | grep -E 'phys_footprint(_peak)?:' | tr -s ' ' | tr '\n' ' ')"
done
curl -s "${OLLAMA_HOST_URL:-http://localhost:11434}/api/ps" | tr ',' '\n' | grep -E '"(name|size|size_vram|context_length)"'
