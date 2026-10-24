"""Blind review of S3 answers (RUBRIC.md): anonymise, then un-blind the reviewer's scores.

    # 1. Build the packet. The mapping goes somewhere the reviewer is never pointed at.
    python spikes/s3/blind.py pack --packet review/packet.md --mapping /tmp/mapping.json \
        spikes/s3/results/reference/<label>/*.json

    # 2. The reviewer fills scores.json (one object per answer id), seeing only packet.md.

    # 3. Un-blind and aggregate per model.
    python spikes/s3/blind.py unblind --mapping /tmp/mapping.json --scores scores.json \
        --out spikes/s3/results/blind_review.json

Refusals (an exact NO_ANSWER) are left out of the packet: there is nothing to judge.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import secrets
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
THINK_BLOCK = re.compile(r"<think>.*?(</think>|\Z)", re.S)


def pack(args: argparse.Namespace) -> None:
    prompts = {p["id"]: p for p in json.loads((HERE / "prompts.json").read_text(encoding="utf-8"))["prompts"]}
    answers: dict[str, list[dict]] = {pid: [] for pid in prompts}
    for path in args.results:
        run = json.loads(Path(path).read_text(encoding="utf-8"))
        for r in run["results"]:
            text = THINK_BLOCK.sub("", r["output"]).strip()
            if text and text != "NO_ANSWER":
                answers[r["id"]].append({"model": run["run"]["model"], "provider": run["run"]["provider"],
                                         "label": run["run"]["label"], "text": text})
    rng = random.Random(secrets.randbits(64))  # noqa: S311 - shuffling, not crypto; the seed is not saved
    flat = [(pid, a) for pid in answers for a in answers[pid]]
    ids = [f"A{n:02d}" for n in range(1, len(flat) + 1)]
    rng.shuffle(ids)
    mapping = {}
    for (pid, a), aid in zip(flat, ids, strict=True):
        a["id"] = aid
        mapping[aid] = {"prompt": pid, "model": a["model"], "provider": a["provider"], "label": a["label"]}

    rubric = (HERE / "RUBRIC.md").read_text(encoding="utf-8")
    out = [rubric, "\n---\n\n# Items\n"]
    template = []
    for pid, items in answers.items():
        if not items:
            continue
        p = prompts[pid]
        rng.shuffle(items)
        out.append(f"\n## {pid} ({'Arabic' if p['language'] == 'ar' else 'English'} question)\n")
        out.append(f"**Question:** {p['question']}\n")
        out.append("<details><summary>Excerpts</summary>\n")
        for e in p["excerpts"]:
            out.append(f"**[{e['n']}]** {e['title']} — p. {e['page']}\n\n{e['text']}\n")
        out.append("</details>\n")
        for a in sorted(items, key=lambda x: x["id"]):
            out.append(f"\n### {a['id']}\n\n{a['text']}\n")
            template.append({"id": a["id"], "prompt": pid,
                             "fluency": None if p["language"] == "ar" else "n/a",
                             "unsupported_claims": None, "wrong_citation": None,
                             "grounding": None, "answers_question": None, "note": ""})
    Path(args.packet).parent.mkdir(parents=True, exist_ok=True)
    Path(args.packet).write_text("\n".join(out), encoding="utf-8")
    Path(args.packet).with_suffix(".scores-template.json").write_text(
        json.dumps(sorted(template, key=lambda t: t["id"]), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    Path(args.mapping).write_text(json.dumps(mapping, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(flat)} answers packed into {args.packet}; mapping in {args.mapping}")


def unblind(args: argparse.Namespace) -> None:
    mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8"))
    scores = json.loads(Path(args.scores).read_text(encoding="utf-8"))
    per: dict[str, dict[str, list]] = {}
    rows = []
    for s in scores:
        m = mapping[s["id"]]
        key = m["model"] if m["provider"] == "ollama" else f"{m['model']} (hosted)"
        agg = per.setdefault(key, {"fluency": [], "grounding": [], "answers_question": [],
                                   "unsupported_claims": [], "wrong_citation": []})
        for k in agg:
            if isinstance(s.get(k), (int, float)):
                agg[k].append(s[k])
        rows.append({**s, **m})
    summary = {}
    for model, agg in sorted(per.items()):
        summary[model] = {
            "answers_reviewed": len(agg["grounding"]),
            "arabic_fluency_mean": round(statistics.mean(agg["fluency"]), 2) if agg["fluency"] else None,
            "arabic_answers": len(agg["fluency"]),
            "grounding_mean_0_2": round(statistics.mean(agg["grounding"]), 2) if agg["grounding"] else None,
            "answers_question_mean_0_2": round(statistics.mean(agg["answers_question"]), 2) if agg["answers_question"] else None,
            "unsupported_claims_total": sum(agg["unsupported_claims"]),
            "wrong_citations_total": sum(agg["wrong_citation"]),
        }
    Path(args.out).write_text(json.dumps({"summary": summary, "items": sorted(rows, key=lambda r: (r["prompt"], r["model"]))},
                                         ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for model, s in summary.items():
        print(model, s)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack")
    p.add_argument("--packet", required=True)
    p.add_argument("--mapping", required=True)
    p.add_argument("results", nargs="+")
    u = sub.add_parser("unblind")
    u.add_argument("--mapping", required=True)
    u.add_argument("--scores", required=True)
    u.add_argument("--out", required=True)
    args = ap.parse_args()
    pack(args) if args.cmd == "pack" else unblind(args)


if __name__ == "__main__":
    main()
