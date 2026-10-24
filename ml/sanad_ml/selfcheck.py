"""Measure int8 fidelity on this machine: `python -m sanad_ml.selfcheck` (in the ml container).

The build exports the models, quantises them to int8 and records the original fp32 outputs for
a few check inputs in `reference.json` next to each model. CPU int8 kernels differ between
arm64 and x86 (with or without VNNI), so this re-runs those inputs here and compares. Run it
once on the server that hosts Sanad. Exit status 1 if the models disagree with fp32 by more
than the build's own gate allows.
"""

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from sanad_ml.engine import Engine, OnnxEngine
from sanad_ml.main import config_from_env

# The same limits the build gate uses (ml/build/export_models.py).
MIN_COSINE = 0.95
MAX_SCORE_DIFF = 0.15


def measure(engine: Engine, models_dir: Path) -> dict[str, Any]:
    embed = json.loads((models_dir / "embed" / "reference.json").read_text(encoding="utf-8"))
    vectors = engine.embed(embed["inputs"])
    reference = np.asarray(embed["fp32"], dtype=np.float32)
    reference /= np.linalg.norm(reference, axis=1, keepdims=True)
    cosine = (vectors * reference).sum(axis=1)

    rerank = json.loads((models_dir / "rerank" / "reference.json").read_text(encoding="utf-8"))
    query = rerank["inputs"][0][0]
    scores = np.asarray(engine.rerank(query, [passage for _, passage in rerank["inputs"]]))
    difference = np.abs(scores - np.asarray(rerank["fp32"]))
    result = {
        "embed_min_cosine_vs_fp32": round(float(cosine.min()), 4),
        "embed_mean_cosine_vs_fp32": round(float(cosine.mean()), 4),
        "rerank_max_score_diff_vs_fp32": round(float(difference.max()), 4),
    }
    result["ok"] = bool(cosine.min() >= MIN_COSINE and difference.max() <= MAX_SCORE_DIFF)
    return result


def main() -> int:
    config = config_from_env()
    result = measure(OnnxEngine(config), config.models_dir)
    sys.stdout.write(json.dumps(result) + "\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
