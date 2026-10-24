"""The on-machine fidelity check, against the tiny generated models of test_engine."""

import json
from pathlib import Path

import numpy as np
import pytest

from sanad_ml.engine import EngineConfig, OnnxEngine
from sanad_ml.selfcheck import main, measure
from tests.test_engine import models_dir  # noqa: F401  (fixture)

TEXTS = ["water points", "girls school التعليم", "budget 2021"]
QUERY = "girls"
PASSAGES = ["water points", "budget", "school"]


def write_references(directory: Path, *, skew: float = 0.0) -> None:
    engine = OnnxEngine(EngineConfig(models_dir=directory, threads=1))
    vectors = engine.embed(TEXTS) + skew
    scores = [s + skew for s in engine.rerank(QUERY, PASSAGES)]
    (directory / "embed" / "reference.json").write_text(
        json.dumps({"inputs": TEXTS, "fp32": vectors.tolist()}), "utf-8"
    )
    (directory / "rerank" / "reference.json").write_text(
        json.dumps({"inputs": [[QUERY, p] for p in PASSAGES], "fp32": scores}), "utf-8"
    )


def test_matching_models_pass(models_dir: Path) -> None:  # noqa: F811
    write_references(models_dir)
    result = measure(OnnxEngine(EngineConfig(models_dir=models_dir, threads=1)), models_dir)
    assert result["ok"] is True
    assert result["embed_min_cosine_vs_fp32"] == pytest.approx(1.0, abs=1e-4)
    assert result["rerank_max_score_diff_vs_fp32"] == pytest.approx(0.0, abs=1e-4)


def test_drifted_models_fail_with_exit_status_1(
    models_dir: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_references(models_dir, skew=0.5)
    monkeypatch.setenv("ML_MODELS_DIR", str(models_dir))
    monkeypatch.setenv("ML_THREADS", "1")
    assert main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert result["rerank_max_score_diff_vs_fp32"] == pytest.approx(0.5, abs=1e-4)
    assert np.isfinite(result["embed_mean_cosine_vs_fp32"])
