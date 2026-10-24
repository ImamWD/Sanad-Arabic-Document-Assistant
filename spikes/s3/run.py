"""S3 local LLM shoot-out: run the fixed RAG prompts against one or more models and score them.

Stdlib only, so it runs in backend-dev as is. From the repo root:

    # host-native Ollama (Metal on a Mac), first 3 prompts
    docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm backend-dev \
        python spikes/s3/run.py --model gemma4:12b-it-qat --prompts 3

    # the same host Ollama, CPU only (options.num_gpu = 0)
    ... python spikes/s3/run.py --model gemma4:12b-it-qat --cpu --label "Apple M5 CPU"

    # another Ollama on the LAN (e.g. the owner's RTX 5080 PC)
    ... python spikes/s3/run.py --model gemma4:12b-it-qat --target http://192.168.1.20:11434 --label "RTX 5080"

    # free hosted reference model; synthetic seed prompts only (CLAUDE.md), key from the env
    ... python spikes/s3/run.py --provider openai_compat --model gemma-4-31b-it

Scores follow the SYSTEM_DESIGN §6 contract and its post-validation: markers outside 1..K are
dropped, and an answer with no surviving marker counts as a refusal. Timings come from Ollama's
own response fields plus a client-side time to first content token. Each prompt is preceded by a
tiny "cache-buster" request, so prompt processing is always measured cold (no prefix reuse).

Results go to spikes/s3/results/latest/ (git-ignored) unless --out is given. If a committed
reference run exists for the same model and mode, the per-prompt scores are compared with it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROMPTS = HERE / "prompts.json"
REFERENCE = HERE / "results" / "reference"
DEFAULT_OUT = HERE / "results" / "latest"
GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"

_ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_GROUP_SEP = re.compile(r"(?<=\d)[,٬](?=\d)")
MARKER = re.compile(r"\[(\d+)\]")
# Things that look like citation markers but break the [n] contract: [1, 2], [1-3], [١], 【1】.
NONSTANDARD_MARKER = re.compile(r"\[\s*\d+\s*[,،\-–]\s*\d+[^\]]*\]|\[[٠-٩]+\]|【\d+】")
THINK_BLOCK = re.compile(r"<think>.*?(</think>|\Z)", re.S)
SENTINEL = "NO_ANSWER"
# A "soft refusal" says in prose that the excerpts lack the answer instead of emitting the
# sentinel. With a citation attached, production would show it as an answer. Informational only.
SOFT_REFUSAL_PHRASES = [
    "لا توجد معلومات", "لا تتوفر معلومات", "لا تتضمن", "لا تحتوي", "لا تذكر", "لم تذكر", "لم يرد",
    "لم أجد", "no information", "do not contain", "does not contain", "do not mention",
    "does not mention", "not mentioned", "not provided", "not specified",
]


def norm_digits(text: str) -> str:
    """Digits and separators only (CLAUDE.md #5: no letter folding outside sanad.text.arabic)."""
    return _GROUP_SEP.sub("", text.translate(_ARABIC_INDIC).replace("٫", "."))


def has_fact(text: str, fact: str) -> bool:
    return re.search(rf"(?<![\d.]){re.escape(norm_digits(fact))}(?!\d)", norm_digits(text)) is not None


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", norm_digits(MARKER.sub(" ", text))))


def split_sentences(text: str) -> list[str]:
    parts = [p for p in re.split(r"(?<=[.!?؟])\s+|\n+", text) if p.strip()]
    out: list[str] = []
    for part in parts:
        lead = re.match(r"^\s*((?:\[\d+\]\s*)+)", part)
        if lead and out:  # "… sentence. [3] Next …": the marker belongs to the previous sentence
            out[-1] += " " + lead.group(1).strip()
            part = part[lead.end():]
        if len(re.findall(r"\w", part)) >= 12:
            out.append(part.strip())
    return out


def arabic_share(text: str) -> float:
    ar = len(re.findall(r"[ء-ي]", text))
    lat = len(re.findall(r"[A-Za-z]", MARKER.sub("", text)))
    return ar / (ar + lat) if ar + lat else 0.0


def score(prompt: dict, raw: str) -> dict[str, Any]:
    """Score one answer. 'outcome' is what production would do after §6 post-validation."""
    k = len(prompt["excerpts"])
    text = THINK_BLOCK.sub("", raw).strip()
    supporting = {e["n"] for e in prompt["excerpts"] if e["supports"]}
    markers = [int(m) for m in MARKER.findall(text)]
    valid = [m for m in markers if 1 <= m <= k]
    sentinel_exact = text == SENTINEL
    outcome = "no_answer" if sentinel_exact or not valid else "answered"
    s: dict[str, Any] = {
        "sentinel_strict": raw.strip() == SENTINEL,  # what a raw string compare would see
        "sentinel_exact": sentinel_exact,  # after stripping think tags and whitespace
        "sentinel_mixed": SENTINEL in text and not sentinel_exact,
        "had_think_tags": "<think>" in raw,
        "outcome": outcome,
        "refusal_reason": ("sentinel" if sentinel_exact else "no_valid_citation") if outcome == "no_answer" else None,
        "markers": len(markers),
        "markers_out_of_range": len(markers) - len(valid),
        "markers_nonstandard": len(NONSTANDARD_MARKER.findall(text)),
        "cited_excerpts": sorted(set(valid)),
        "soft_refusal": not sentinel_exact and any(ph in text.lower() for ph in SOFT_REFUSAL_PHRASES),
    }
    if prompt["expected_outcome"] == "no_answer":
        s["pass"] = sentinel_exact
        return s
    sentences = split_sentences(text) if not sentinel_exact else []
    facts = {f: has_fact(text, f) for f in prompt["must_include"]}
    excerpt_numbers = set().union(*(numbers(e["text"]) for e in prompt["excerpts"]), numbers(prompt["question"]))
    s.update({
        "facts": facts,
        "facts_ok": all(facts.values()) and not sentinel_exact,
        "cites_support": bool(supporting & set(valid)),
        "cited_sentence_ratio": round(sum(bool(MARKER.search(x)) for x in sentences) / len(sentences), 2) if sentences else 0.0,
        "numbers_not_in_excerpts": sorted(numbers(text) - excerpt_numbers),
        "language_ok": (arabic_share(text) >= 0.6) if prompt["language"] == "ar" else (arabic_share(text) <= 0.4),
    })
    if prompt.get("injection"):
        inj = prompt["injection"]
        followed = [c for c in inj["canaries"] + inj["false_facts"] if c in text]
        s["injection_followed"] = followed
        s["injection_resisted"] = not followed and s["facts_ok"] and outcome == "answered"
    s["pass"] = (outcome == "answered" and s["facts_ok"] and s["cites_support"] and s["language_ok"]
                 and s.get("injection_resisted", True))
    return s


# --------------------------------------------------------------------------------------- HTTP


def post_json(url: str, body: dict, headers: dict | None = None, timeout: float = 900) -> Any:
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def get_json(url: str, timeout: float = 30) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def stream_lines(url: str, body: dict, headers: dict | None = None, timeout: float = 1800):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for line in resp:
            line = line.strip()
            if line:
                yield line.decode()


def first_content_seen(content: str) -> bool:
    """True once the answer has a visible character outside any (possibly unclosed) think block."""
    return bool(THINK_BLOCK.sub("", content).strip())


class Ollama:
    def __init__(self, target: str, num_ctx: int, num_predict: int, cpu: bool, seed: int, keep_alive: str):
        self.base = target.rstrip("/")
        self.options: dict[str, Any] = {"temperature": 0, "seed": seed, "num_ctx": num_ctx, "num_predict": num_predict}
        if cpu:
            self.options["num_gpu"] = 0
        self.keep_alive = keep_alive

    def version(self) -> str:
        return get_json(f"{self.base}/api/version").get("version", "?")

    def info(self, model: str) -> dict[str, Any]:
        show = post_json(f"{self.base}/api/show", {"model": model})
        mi = show.get("model_info", {})
        arch = mi.get("general.architecture", "")
        return {
            "details": show.get("details", {}),
            "capabilities": show.get("capabilities", []),
            "architecture": arch,
            "parameter_count": mi.get("general.parameter_count"),
            "context_length": mi.get(f"{arch}.context_length"),
            "expert_count": mi.get(f"{arch}.expert_count"),
            "expert_used_count": mi.get(f"{arch}.expert_used_count"),
            "license_first_line": (show.get("license") or "").strip().splitlines()[0][:120] if show.get("license") else None,
        }

    def _body(self, model: str, messages: list[dict], think: bool | None, **opts: Any) -> dict:
        body = {"model": model, "messages": messages, "stream": True, "keep_alive": self.keep_alive,
                "options": {**self.options, **opts}}
        if think is not None:
            body["think"] = think
        return body

    def bust_cache(self, model: str, think: bool | None) -> None:
        msgs = [{"role": "system", "content": "Cache reset."}, {"role": "user", "content": "ok"}]
        for _ in stream_lines(f"{self.base}/api/chat", self._body(model, msgs, think, num_predict=1)):
            pass

    def chat(self, model: str, system: str, user: str, think: bool | None) -> dict[str, Any]:
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        t0 = time.perf_counter()
        ttft = None
        content, thinking, final = "", "", {}
        for line in stream_lines(f"{self.base}/api/chat", self._body(model, msgs, think)):
            chunk = json.loads(line)
            if "error" in chunk:
                raise RuntimeError(chunk["error"])
            msg = chunk.get("message", {})
            content += msg.get("content", "")
            thinking += msg.get("thinking", "") or ""
            if ttft is None and first_content_seen(content):
                ttft = time.perf_counter() - t0
            if chunk.get("done"):
                final = chunk
        wall = time.perf_counter() - t0
        ns = 1e9
        pe_n, pe_d = final.get("prompt_eval_count", 0), final.get("prompt_eval_duration", 0) / ns
        ev_n, ev_d = final.get("eval_count", 0), final.get("eval_duration", 0) / ns
        return {
            "output": content,
            "thinking_chars": len(thinking),
            "done_reason": final.get("done_reason"),
            "timing": {
                "wall_s": round(wall, 2),
                "ttft_s": round(ttft, 2) if ttft is not None else None,
                "load_s": round(final.get("load_duration", 0) / ns, 2),
                "prompt_tokens": pe_n,
                "prompt_eval_s": round(pe_d, 2),
                "pp_tok_s": round(pe_n / pe_d, 1) if pe_d else None,
                "output_tokens": ev_n,
                "eval_s": round(ev_d, 2),
                "gen_tok_s": round(ev_n / ev_d, 1) if ev_d else None,
            },
        }

    def memory(self, model: str) -> dict[str, Any]:
        for m in get_json(f"{self.base}/api/ps").get("models", []):
            if m.get("name") == model or m.get("model") == model:
                size, vram = m.get("size", 0), m.get("size_vram", 0)
                return {"size_gb": round(size / 1e9, 2), "size_vram_gb": round(vram / 1e9, 2),
                        "fully_offloaded": size > 0 and vram >= size, "context_length": m.get("context_length")}
        return {}


class OpenAICompat:
    """Generic OpenAI-compatible chat endpoint (default: Google Gemini API free tier).

    Synthetic seed data only: main() refuses to call it unless every excerpt comes from the seed
    manifest. The key is read from OPENAI_COMPAT_API_KEY and is never printed or written out.
    """

    def __init__(self, base: str, key: str, max_tokens: int, seed: int, reasoning_effort: str | None):
        self.base = base.rstrip("/")
        self.headers = {"Authorization": f"Bearer {key}"}
        self.max_tokens = max_tokens
        self.seed = seed
        self.reasoning_effort = reasoning_effort

    def chat(self, model: str, system: str, user: str, think: bool | None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model, "stream": True, "stream_options": {"include_usage": True},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0, "max_tokens": self.max_tokens,
        }
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        t0 = time.perf_counter()
        ttft, content, usage = None, "", {}
        for line in stream_lines(f"{self.base}/chat/completions", body, self.headers):
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            for choice in chunk.get("choices", []):
                content += (choice.get("delta") or {}).get("content") or ""
            if ttft is None and first_content_seen(content):
                ttft = time.perf_counter() - t0
            usage = chunk.get("usage") or usage
        wall = time.perf_counter() - t0
        return {
            "output": content,
            "thinking_chars": None,
            "done_reason": None,
            "timing": {"wall_s": round(wall, 2), "ttft_s": round(ttft, 2) if ttft is not None else None,
                       "prompt_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens"),
                       "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")},
        }


# --------------------------------------------------------------------------------------- run


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")


def assert_synthetic(data: dict) -> None:
    manifest = json.loads((ROOT / "seed" / "manifest.json").read_text(encoding="utf-8"))
    seed_ids = {d.get("doc_id") or d.get("id") for d in manifest.get("documents", [])}
    used = {e["doc_id"] for p in data["prompts"] for e in p["excerpts"]}
    if not data.get("synthetic_seed_only") or not used <= seed_ids:
        sys.exit("Refusing: hosted models may only receive synthetic seed data (CLAUDE.md).")


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, round(q * (len(ordered) - 1) + 0.4999)))
    return ordered[idx]  # nearest-rank (conservative)


def summarise(rows: list[dict]) -> dict[str, Any]:
    ans = [r for r in rows if r["expected_outcome"] == "answered"]
    una = [r for r in rows if r["expected_outcome"] == "no_answer"]
    answered = [r for r in rows if r["score"]["outcome"] == "answered"]
    t = [r["timing"] for r in rows]

    def med(key: str) -> float | None:
        vals = [x[key] for x in t if x.get(key) is not None]
        return round(statistics.median(vals), 1) if vals else None

    inj = [r for r in rows if "injection_resisted" in r["score"]]
    return {
        "prompts": len(rows),
        "pass": sum(r["score"]["pass"] for r in rows),
        "answerable_pass": f"{sum(r['score']['pass'] for r in ans)}/{len(ans)}",
        "facts_ok": f"{sum(r['score'].get('facts_ok', False) for r in ans)}/{len(ans)}",
        "false_refusals": sum(r["score"]["outcome"] == "no_answer" for r in ans),
        "correct_refusals": f"{sum(r['score']['sentinel_exact'] for r in una)}/{len(una)}",
        "soft_refusals": sum(r["score"]["soft_refusal"] for r in rows),
        "unanswerable_answered_with_citation": sum(r["score"]["outcome"] == "answered" for r in una),
        "refusals_strict": f"{sum(r['score']['sentinel_strict'] for r in una)}/{len(una)}",
        "cites_support": f"{sum(r['score'].get('cites_support', False) for r in ans)}/{len(ans)}",
        "cited_sentence_ratio": round(statistics.mean(r["score"]["cited_sentence_ratio"] for r in ans if "cited_sentence_ratio" in r["score"]), 2) if ans else None,
        "markers_out_of_range": sum(r["score"]["markers_out_of_range"] for r in rows),
        "markers_nonstandard": sum(r["score"]["markers_nonstandard"] for r in rows),
        "answers_with_numbers_not_in_excerpts": sum(bool(r["score"].get("numbers_not_in_excerpts")) for r in answered),
        "language_ok": f"{sum(r['score'].get('language_ok', False) for r in ans)}/{len(ans)}",
        "injection_resisted": (all(r["score"]["injection_resisted"] for r in inj) if inj else None),
        "median_prompt_tokens": med("prompt_tokens"),
        "median_pp_tok_s": med("pp_tok_s"),
        "median_gen_tok_s": med("gen_tok_s"),
        "median_output_tokens": med("output_tokens"),
        "median_ttft_s": med("ttft_s"),
        "median_wall_s": med("wall_s"),
        "p90_wall_s": percentile([x["wall_s"] for x in t], 0.9),
    }


def find_reference(model: str, provider: str, cpu: bool, label: str, written: Path) -> dict | None:
    if not REFERENCE.exists():
        return None
    name = f"{slug(model)}{'__cpu' if cpu else ''}.json"
    candidates = [REFERENCE / slug(label) / name] + sorted(REFERENCE.glob(f"*/{name}"))
    for path in candidates:
        if path.exists() and path.resolve() != written.resolve():
            ref = json.loads(path.read_text(encoding="utf-8"))
            if ref["run"]["provider"] == provider:
                ref["_path"] = str(path.relative_to(ROOT))
                return ref
    return None


def fmt(v: Any) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    return "-" if v is None else str(v)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", help="model name or tag; comma-separate several")
    ap.add_argument("--rescore", nargs="+", metavar="RESULT_JSON", help="re-score saved runs with the current scorer; no model calls")
    ap.add_argument("--prompts", type=int, default=None, help="run only the first N prompts")
    ap.add_argument("--ids", default=None, help="comma-separated prompt ids, e.g. P02,P08")
    ap.add_argument("--provider", choices=["ollama", "openai_compat"], default="ollama")
    ap.add_argument("--target", default=None, help="Ollama base URL (default $OLLAMA_BASE_URL) or OpenAI-compatible base URL")
    ap.add_argument("--cpu", action="store_true", help="Ollama only: options.num_gpu = 0 (CPU-only timings)")
    ap.add_argument("--label", default=None, help="hardware label stored with the results, e.g. 'Apple M5 GPU (Metal)'")
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--num-predict", type=int, default=768)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--keep-alive", default="15m")
    ap.add_argument("--no-cache-bust", action="store_true", help="let Ollama reuse the shared system-prompt prefix")
    ap.add_argument("--reasoning-effort", default=None, help="openai_compat only, e.g. low (Gemini 3.x can't turn reasoning off)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="results directory (default: git-ignored results/latest)")
    args = ap.parse_args()

    data = json.loads(PROMPTS.read_text(encoding="utf-8"))
    if args.rescore:
        by_id = {p["id"]: p for p in data["prompts"]}
        for path in map(Path, args.rescore):
            run = json.loads(path.read_text(encoding="utf-8"))
            for r in run["results"]:
                r["score"] = score(by_id[r["id"]], r["output"])
            run["summary"] = summarise(run["results"])
            path.write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"{run['run']['model']:28} {run['run']['label']:22} pass={run['summary']['pass']}/{run['summary']['prompts']}")
        return
    if not args.model:
        ap.error("--model is required")
    prompts = data["prompts"]
    if args.ids:
        wanted = args.ids.split(",")
        prompts = [p for p in prompts if p["id"] in wanted]
    if args.prompts:
        prompts = prompts[: args.prompts]
    prompts_sha = hashlib.sha256(PROMPTS.read_bytes()).hexdigest()[:12]

    if args.provider == "openai_compat":
        key = os.environ.get("OPENAI_COMPAT_API_KEY", "")
        if not key:
            print("OPENAI_COMPAT_API_KEY is not set: skipping the hosted reference run.")
            return
        assert_synthetic(data)
        target = args.target or os.environ.get("OPENAI_COMPAT_BASE_URL") or GEMINI_OPENAI_BASE
        client: Any = OpenAICompat(target, key, max(args.num_predict, 4096), args.seed, args.reasoning_effort)
        label = args.label or f"hosted: {urlparse(target).hostname}"
        server_version = None
    else:
        target = args.target or os.environ.get("OLLAMA_BASE_URL") or "http://host.docker.internal:11434"
        client = Ollama(target, args.num_ctx, args.num_predict, args.cpu, args.seed, args.keep_alive)
        label = args.label or ("CPU only (num_gpu=0)" if args.cpu else "default offload")
        server_version = client.version()

    out_dir = Path(args.out) / slug(label)
    out_dir.mkdir(parents=True, exist_ok=True)

    for model in [m.strip() for m in args.model.split(",") if m.strip()]:
        print(f"\n== {model}  [{label}]  provider={args.provider}  prompts={len(prompts)}  prompts.json={prompts_sha}")
        info: dict[str, Any] = {}
        think: bool | None = None
        if args.provider == "ollama":
            info = client.info(model)
            think = False if "thinking" in info["capabilities"] else None
            print(f"   {info['details'].get('parameter_size')} {info['details'].get('quantization_level')} "
                  f"{info['details'].get('format')} arch={info['architecture']} think={think}")
            # Warm-up: loads the model with the run's options (num_ctx, num_gpu) so load time
            # isn't charged to the first prompt.
            client.bust_cache(model, think)
        rows: list[dict] = []
        memory: dict[str, Any] = {}
        for p in prompts:
            if args.provider == "ollama" and not args.no_cache_bust:
                client.bust_cache(model, think)
            try:
                res = client.chat(model, data["system_prompt"], p["user_message"], think)
            except (urllib.error.URLError, RuntimeError, TimeoutError) as exc:
                detail = exc.read().decode(errors="replace")[:300] if isinstance(exc, urllib.error.HTTPError) else str(exc)
                print(f"   {p['id']} ERROR {type(exc).__name__}: {detail}")
                continue
            if args.provider == "ollama":
                if not memory:
                    memory = client.memory(model)
                limit = args.num_ctx - args.num_predict
                if res["timing"]["prompt_tokens"] >= limit:
                    print(f"   {p['id']} WARNING prompt_tokens {res['timing']['prompt_tokens']} >= num_ctx-num_predict {limit}: may be truncated")
            sc = score(p, res["output"])
            rows.append({"id": p["id"], "language": p["language"], "expected_outcome": p["expected_outcome"], **res, "score": sc})
            tm = res["timing"]
            extra = ""
            if "facts_ok" in sc:
                extra = f"facts={fmt(sc['facts_ok'])} cites_gold={fmt(sc['cites_support'])} cited_sent={sc['cited_sentence_ratio']}"
            if "injection_resisted" in sc:
                extra += f" injection_resisted={fmt(sc['injection_resisted'])}"
            print(f"   {p['id']} {p['language']} expect={p['expected_outcome']:9} got={sc['outcome']:9} "
                  f"pass={fmt(sc['pass']):3} {extra}")
            print(f"        prompt={fmt(tm.get('prompt_tokens'))} tok  pp={fmt(tm.get('pp_tok_s'))} tok/s  "
                  f"out={fmt(tm.get('output_tokens'))} tok  gen={fmt(tm.get('gen_tok_s'))} tok/s  "
                  f"ttft={fmt(tm.get('ttft_s'))} s  total={tm['wall_s']} s")
        if not rows:
            continue
        summary = summarise(rows)
        result = {
            "run": {
                "model": model, "provider": args.provider, "label": label, "cpu": args.cpu,
                "target_host": urlparse(target).hostname, "server_version": server_version,
                "options": getattr(client, "options", {"max_tokens": getattr(client, "max_tokens", None)}),
                "think": think, "cache_bust": not args.no_cache_bust,
                "date_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "prompts_sha256_12": prompts_sha, "prompt_ids": [p["id"] for p in prompts],
            },
            "model_info": info,
            "memory": memory,
            "summary": summary,
            "results": rows,
        }
        path = out_dir / f"{slug(model)}{'__cpu' if args.cpu else ''}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"   summary: " + "  ".join(f"{k}={fmt(v)}" for k, v in summary.items()))
        if memory:
            print(f"   memory: {memory}")
        print(f"   wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")

        ref = find_reference(model, args.provider, args.cpu, label, path)
        if ref:
            by_id = {r["id"]: r for r in ref["results"]}
            same = 0
            print(f"   compare with reference {ref['_path']} ({ref['run']['label']}, {ref['run']['date_utc']}):")
            for r in rows:
                old = by_id.get(r["id"])
                if not old:
                    continue
                keys = ("outcome", "pass", "facts_ok", "cites_support", "injection_resisted")
                a = {k: r["score"].get(k) for k in keys}
                b = {k: old["score"].get(k) for k in keys}
                same += a == b
                print(f"     {r['id']} {'MATCH' if a == b else 'DIFF '} now={a} reference={b}")
            print(f"   {same}/{len(rows)} prompts score the same as the reference")


if __name__ == "__main__":
    main()
