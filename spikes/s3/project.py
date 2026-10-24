"""Project S3 answer times onto GPU cards we can't run here (estimates, clearly labelled).

    # 1. While the model is still pulled: record its tensor profile (weights read per token,
    #    active parameters, KV-cache size). Saved to results/model_profiles.json.
    python spikes/s3/project.py profile --model gemma4:12b-it-qat

    # 2. Estimate per-prompt LLM time on each card from the measured token counts of a run.
    python spikes/s3/project.py estimate spikes/s3/results/reference/<label>/*.json

Method (each assumption is printed with the table):
- Generation is memory-bandwidth bound: tok/s = eta x bandwidth / (weights read per token + KV
  read per token). eta is calibrated on the card's own measured llama.cpp tg128 for Llama-2-7B
  Q4_0 (ggml-org/llama.cpp discussion 15013).
- Prompt processing is compute bound: tok/s = measured pp512 (same source) x (Llama-2-7B
  active params / model active params) x a long-context factor, x a MoE factor for MoE models.
- Per prompt: the measured prompt tokens and output tokens of the run (verbosity matters), and
  total = prompt time + output tokens / gen tok/s + RETRIEVAL_S for embedding, search and rerank.
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

# Reference model for calibration: Llama-2-7B Q4_0, as benchmarked by llama-bench.
REF_WEIGHTS_GB = 3.80  # read per generated token (all layers + output head; embedding lookup excluded)
REF_ACTIVE_B = 6.61  # non-embedding parameters, billions

# Measured llama-bench numbers (FA on) from ggml-org/llama.cpp discussion 15013, Llama-2-7B Q4_0.
CARDS = {
    "RTX PRO 4000 Blackwell 24 GB": {"bandwidth_gbs": 672, "pp512": 5674.44, "tg128": 136.38, "vram_gb": 24},
    "RTX 5080 16 GB (owner's dev PC)": {"bandwidth_gbs": 960, "pp512": 9487.70, "tg128": 184.68, "vram_gb": 16},
}
CTX_FACTOR = 0.85  # prompt processing at ~4.5k tokens vs pp512 (attention grows with context); assumed
MOE_PP_FACTOR = 0.5  # MoE prompt processing reaches about half the dense rate per active param; assumed
OVERHEAD_S = 0.3  # request handling, sampling, first-token latency beyond prompt processing; assumed
RETRIEVAL_S = 2.0  # question embedding + hybrid search + rerank of 30 chunks on GPU/CPU; upper estimate (D3: 1-2 s)
ML_ON_GPU_GB = 3.0  # bge-m3 + bge-reranker-v2-m3 on the same card, if placed there


def show(base: str, model: str) -> dict:
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


def kv_read_gb(p: dict, ctx: int) -> float:
    return sum(layer["bytes_per_token"] * (min(ctx, layer["window"]) if layer["window"] else ctx)
               for layer in p["kv_layers"]) / 1e9


def estimate_prompt(p: dict, card: dict, prompt_tokens: int, output_tokens: int) -> dict:
    eta = card["tg128"] * REF_WEIGHTS_GB / card["bandwidth_gbs"]
    ctx = prompt_tokens + output_tokens / 2
    gen = eta * card["bandwidth_gbs"] / (p["read_per_token_gb"] + kv_read_gb(p, int(ctx)))
    pp = card["pp512"] * (REF_ACTIVE_B / p["active_params_b"]) * CTX_FACTOR * (MOE_PP_FACTOR if p["moe"] else 1.0)
    llm = prompt_tokens / pp + output_tokens / gen + OVERHEAD_S
    return {"pp_tok_s": pp, "gen_tok_s": gen, "ttft_s": prompt_tokens / pp + OVERHEAD_S, "llm_s": llm,
            "total_s": llm + RETRIEVAL_S}


def nearest_rank(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("profile")
    pr.add_argument("--model", required=True)
    pr.add_argument("--target", default=os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434"))
    es = sub.add_parser("estimate")
    es.add_argument("results", nargs="+")
    es.add_argument("--json-out", default=None)
    args = ap.parse_args()

    profiles = json.loads(PROFILES.read_text(encoding="utf-8")) if PROFILES.exists() else {}
    if args.cmd == "profile":
        p = profile(args.target, args.model)
        profiles[args.model] = p
        PROFILES.parent.mkdir(parents=True, exist_ok=True)
        PROFILES.write_text(json.dumps(profiles, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in p.items() if k != "kv_layers"}, indent=1),
              f"\nKV read at 4.5k ctx: {kv_read_gb(p, 4500):.3f} GB/token")
        return

    print("ESTIMATES, not measurements. Assumptions: eta from each card's measured Llama-2-7B Q4_0 tg128; "
          f"pp scaled by active params x {CTX_FACTOR} (long context) x {MOE_PP_FACTOR} if MoE; "
          f"+{OVERHEAD_S} s overhead; +{RETRIEVAL_S} s retrieval; f16 KV.\n")
    out = {}
    for path in args.results:
        run = json.loads(Path(path).read_text(encoding="utf-8"))
        model = run["run"]["model"]
        p = profiles.get(model)
        if not p:
            print(f"{model}: no profile (run `project.py profile --model {model}` while it is pulled)")
            continue
        mem = run.get("memory", {})
        for card_name, card in CARDS.items():
            per = [estimate_prompt(p, card, r["timing"]["prompt_tokens"], r["timing"]["output_tokens"])
                   for r in run["results"]]
            totals = [x["total_s"] for x in per]
            row = {
                "card": card_name, "model": model,
                "gen_tok_s": round(sum(x["gen_tok_s"] for x in per) / len(per), 1),
                "pp_tok_s": round(sum(x["pp_tok_s"] for x in per) / len(per)),
                "median_ttft_s": round(sorted(x["ttft_s"] for x in per)[len(per) // 2], 2),
                "median_total_s": round(sorted(totals)[len(totals) // 2], 1),
                "p90_total_s": round(nearest_rank(totals, 0.9), 1),
                "max_total_s": round(max(totals), 1),
                "meets_15s_p90": nearest_rank(totals, 0.9) <= 15,
                "llm_memory_gb_at_8k_ctx": mem.get("size_gb"),
                "fits_with_ml_on_gpu": (mem.get("size_gb") or 99) + ML_ON_GPU_GB <= card["vram_gb"] * 0.95,
            }
            out.setdefault(model, []).append(row)
            print(f"{card_name:34} {model:28} gen={row['gen_tok_s']:6} tok/s pp={row['pp_tok_s']:6} tok/s "
                  f"ttft~{row['median_ttft_s']:5} s median~{row['median_total_s']:5} s p90~{row['p90_total_s']:5} s "
                  f"max~{row['max_total_s']:5} s  meets_p90<=15s={row['meets_15s_p90']}  "
                  f"mem@8k={row['llm_memory_gb_at_8k_ctx']} GB fits_with_ml={row['fits_with_ml_on_gpu']}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
