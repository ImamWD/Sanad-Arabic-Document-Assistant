"""Record a model's tensor profile from Ollama, for the S3 memory budget.

    python spikes/s3/model_profile.py --model gemma4:12b-it-qat [--num-ctx 8192]

Reads `/api/show` (verbose) and saves to results/model_profiles.json:
- weights on disk, split into text weights and vision/audio towers
- weights read per generated token (MoE experts scaled by experts-used / experts)
- active parameters
- KV-cache bytes per context token, per layer
- the licence fields in the GGUF

It prints the KV cache Ollama allocates at --num-ctx: f16, sliding-window layers capped at their
window, and no KV for hybrid models' recurrent layers. Run it while the model is still pulled.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILES = HERE / "results" / "model_profiles.json"

# Bits per weight of GGML tensor types (block size overhead included).
BPW = {
    "F32": 32, "F16": 16, "BF16": 16, "Q8_0": 8.5, "Q8_1": 9, "Q6_K": 6.5625, "Q5_K": 5.5, "Q5_0": 5.5,
    "Q5_1": 6, "Q4_K": 4.5, "Q4_0": 4.5, "Q4_1": 5, "Q3_K": 3.4375, "Q2_K": 2.625, "IQ4_NL": 4.5,
    "IQ4_XS": 4.25, "MXFP4": 4.25, "I8": 8, "I16": 16, "I32": 32,
}
VISION_PREFIXES = ("v.", "mm.", "vision", "a.", "audio")


def show(base: str, model: str) -> dict:
    if not base.startswith(("http://", "https://")):
        raise SystemExit(f"--target must be an http(s) URL, got {base!r}")
    req = urllib.request.Request(f"{base.rstrip('/')}/api/show", json.dumps({"model": model, "verbose": True}).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def profile(base: str, model: str) -> dict:
    s = show(base, model)
    mi = s["model_info"]
    arch = mi["general.architecture"]
    n_exp = mi.get(f"{arch}.expert_count") or 0
    n_used = mi.get(f"{arch}.expert_used_count") or 0
    names = {t["name"] for t in s["tensors"]}
    tied = "output.weight" not in names
    read_b = active = vision_b = 0.0
    for t in s["tensors"]:
        n = math.prod(t["shape"])
        b = n * BPW.get(t["type"], 16) / 8
        name = t["name"]
        if name.startswith(VISION_PREFIXES):
            vision_b += b
            continue
        if name.startswith("token_embd") or "per_layer_token_embd" in name:
            if name == "token_embd.weight" and tied:  # tied output head reads the whole matrix
                read_b += b
                active += n
            continue
        frac = (n_used / n_exp) if ("_exps" in name and n_exp) else 1.0
        read_b += b * frac
        active += n * frac

    # KV cache bytes per context token, f16, per layer (sliding-window layers capped later).
    layers = mi.get(f"{arch}.block_count")
    kv_heads = mi.get(f"{arch}.attention.head_count_kv")
    heads = mi.get(f"{arch}.attention.head_count")
    emb = mi.get(f"{arch}.embedding_length")
    k_len = mi.get(f"{arch}.attention.key_length") or (emb // heads if emb and isinstance(heads, int) else 128)
    v_len = mi.get(f"{arch}.attention.value_length") or k_len
    per_layer_kv = kv_heads if isinstance(kv_heads, list) else [kv_heads] * layers
    window = mi.get(f"{arch}.attention.sliding_window")
    pattern = mi.get(f"{arch}.attention.sliding_window_pattern")
    full_interval = mi.get(f"{arch}.full_attention_interval")
    kv_layers = []
    for i, h in enumerate(per_layer_kv):
        if not h:
            continue  # no KV (e.g. linear-attention layer)
        if full_interval and (i + 1) % full_interval != 0:
            continue  # hybrid model: recurrent layer, fixed-size state instead of a KV cache
        sliding = bool(pattern[i]) if isinstance(pattern, list) and i < len(pattern) else False
        k = (mi.get(f"{arch}.attention.key_length_swa") or k_len) if sliding else k_len
        v = (mi.get(f"{arch}.attention.value_length_swa") or v_len) if sliding else v_len
        kv_layers.append({"bytes_per_token": h * (k + v) * 2, "window": window if sliding else None})
    file_gb = sum(math.prod(t["shape"]) * BPW.get(t["type"], 16) / 8 for t in s["tensors"]) / 1e9
    return {
        "model": model,
        "architecture": arch,
        "quantization": s["details"].get("quantization_level"),
        "gguf_license": mi.get("general.license"),
        "gguf_license_link": mi.get("general.license.link"),
        "license_text_first_line": next((ln.strip() for ln in (s.get("license") or "").splitlines() if ln.strip()), None),
        "parameter_size": s["details"].get("parameter_size"),
        "moe": bool(n_exp),
        "experts": f"{n_used}/{n_exp}" if n_exp else None,
        "weights_gb_total": round(file_gb, 2),
        "vision_audio_gb": round(vision_b / 1e9, 2),
        "read_per_token_gb": round(read_b / 1e9, 3),
        "active_params_b": round(active / 1e9, 2),
        "kv_layers": kv_layers,
        "kv_note": "f16 KV; sliding-window layers capped at the window; hybrid recurrent layers excluded",
    }


def kv_gb(p: dict, ctx: int) -> float:
    """f16 KV cache for `ctx` tokens (Ollama allocates it for the whole num_ctx up front)."""
    return sum(layer["bytes_per_token"] * (min(ctx, layer["window"]) if layer["window"] else ctx)
               for layer in p["kv_layers"]) / 1e9


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--target", default=os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434"))
    args = ap.parse_args()
    profiles = json.loads(PROFILES.read_text(encoding="utf-8")) if PROFILES.exists() else {}
    p = profile(args.target, args.model)
    profiles[args.model] = p
    PROFILES.parent.mkdir(parents=True, exist_ok=True)
    PROFILES.write_text(json.dumps(profiles, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in p.items() if k != "kv_layers"}, indent=1))
    print(f"KV cache at num_ctx {args.num_ctx}: {kv_gb(p, args.num_ctx):.2f} GB")


if __name__ == "__main__":
    main()
