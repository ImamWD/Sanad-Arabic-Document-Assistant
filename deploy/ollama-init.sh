#!/bin/sh
# ollama-init (docker-compose.yml): make sure the configured model is in the shared
# `ollama_models` volume, then exit. It runs its own private Ollama server, is on the egress
# network only, and never sees a prompt. A model already present needs no network at all.
#
# The default model (S3, PR #5) is gemma4:e4b-it-qat served text-only: Gemma's vision and audio
# projector dropped (the second FROM of its Modelfile), weights memory-mapped (use_mmap) and a
# fixed num_ctx. That keeps the whole stack within ~8 GB of Docker memory, with answers
# byte-identical to the full model on S3's prompts. Any other LLM_MODEL is pulled as it is.
set -eu

TEXT_MODEL=sanad-gemma4-e4b-text

if [ "${LLM_PROVIDER:-ollama}" != "ollama" ]; then
  echo "ollama-init: LLM_PROVIDER=${LLM_PROVIDER}, nothing to pull"
  exit 0
fi

ollama serve >/tmp/ollama-serve.log 2>&1 &
tries=0
until ollama list >/dev/null 2>&1; do
  tries=$((tries + 1))
  if [ "$tries" -gt 60 ]; then
    echo "ollama-init: the private ollama server did not start" >&2
    cat /tmp/ollama-serve.log >&2
    exit 1
  fi
  sleep 1
done

if ollama show "$LLM_MODEL" >/dev/null 2>&1; then
  echo "ollama-init: $LLM_MODEL is present"
  exit 0
fi

if [ "$LLM_MODEL" = "$TEXT_MODEL" ]; then
  echo "ollama-init: pulling $OLLAMA_BASE_MODEL to build $TEXT_MODEL"
  ollama pull "$OLLAMA_BASE_MODEL"
  ollama show "$OLLAMA_BASE_MODEL" --modelfile \
    | awk '/^FROM / { if (seen++) next } { print }' >/tmp/Modelfile
  printf 'PARAMETER use_mmap true\nPARAMETER num_ctx %s\n' "$OLLAMA_NUM_CTX" >>/tmp/Modelfile
  ollama create "$TEXT_MODEL" -f /tmp/Modelfile
else
  echo "ollama-init: pulling $LLM_MODEL"
  ollama pull "$LLM_MODEL"
fi
echo "ollama-init: $LLM_MODEL is ready"
