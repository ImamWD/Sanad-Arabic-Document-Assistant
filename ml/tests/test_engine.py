"""OnnxEngine against a tiny generated model: same inputs, outputs and files as the real export.

The graphs are padding-aware sums of per-token weights, so a correct engine gives the same
result for a text whatever batch it lands in and however much padding that batch needs.
"""

import json
from pathlib import Path

import numpy as np
import onnx
import pytest
from onnx import TensorProto, helper, numpy_helper
from tokenizers import Tokenizer, models, pre_tokenizers, processors

from sanad_ml.engine import EngineConfig, OnnxEngine

WORDS = ["water", "points", "girls", "school", "التعليم", "المياه", "budget", "2021"]
SPECIALS = ["<s>", "<pad>", "</s>", "<unk>"]
VOCAB = {token: index for index, token in enumerate(SPECIALS + WORDS)}
DIM = 3


def _tokenizer() -> Tokenizer:
    tokenizer = Tokenizer(models.WordLevel(VOCAB, unk_token="<unk>"))  # noqa: S106 - a token
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.post_processor = processors.TemplateProcessing(
        single="<s> $A </s>",
        pair="<s> $A </s> </s> $B </s>",
        special_tokens=[("<s>", 0), ("</s>", 2)],
    )
    return tokenizer


def _masked_token_sum(weights: np.ndarray, output: str, reduce_axes: list[int]) -> onnx.ModelProto:
    nodes = [
        helper.make_node("Gather", ["weights", "input_ids"], ["gathered"]),
        helper.make_node("Cast", ["attention_mask"], ["mask_f"], to=TensorProto.FLOAT),
        helper.make_node("Unsqueeze", ["mask_f", "axis2"], ["mask_3d"]),
        helper.make_node("Mul", ["gathered", "mask_3d"], ["masked"]),
        helper.make_node("ReduceSum", ["masked", "reduce"], [output], keepdims=0),
    ]
    graph = helper.make_graph(
        nodes,
        "tiny",
        [
            helper.make_tensor_value_info("input_ids", TensorProto.INT64, ["batch", "seq"]),
            helper.make_tensor_value_info("attention_mask", TensorProto.INT64, ["batch", "seq"]),
        ],
        [helper.make_tensor_value_info(output, TensorProto.FLOAT, None)],
        initializer=[
            numpy_helper.from_array(weights.astype(np.float32), "weights"),
            numpy_helper.from_array(np.array([2], dtype=np.int64), "axis2"),
            numpy_helper.from_array(np.array(reduce_axes, dtype=np.int64), "reduce"),
        ],
    )
    # IR 8 goes with opset 17, as in the real export (onnx's default IR is newer than
    # onnxruntime reads).
    return helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=8)


def _write_model(slot: Path, model: onnx.ModelProto, output: str, dim: int | None) -> None:
    slot.mkdir(parents=True)
    onnx.save(model, slot / "model.onnx")
    _tokenizer().save(str(slot / "tokenizer.json"))
    info = {"name": f"tiny/{slot.name}", "revision": "0" * 40, "variant": "onnx-test"}
    (slot / "model.json").write_text(json.dumps({**info, "output": output, "dim": dim}), "utf-8")


@pytest.fixture
def models_dir(tmp_path: Path) -> Path:
    rng = np.random.default_rng(7)
    embed_weights = rng.normal(size=(len(VOCAB), DIM))
    rerank_weights = np.zeros((len(VOCAB), 1))
    rerank_weights[VOCAB["water"]] = 2.0
    rerank_weights[VOCAB["points"]] = 1.0
    rerank_weights[VOCAB["budget"]] = -3.0
    _write_model(
        tmp_path / "embed", _masked_token_sum(embed_weights, "embedding", [1]), "embedding", DIM
    )
    _write_model(
        tmp_path / "rerank", _masked_token_sum(rerank_weights, "logit", [1, 2]), "logit", None
    )
    return tmp_path


def _engine(
    models_dir: Path,
    *,
    batch_size: int = 1,
    embed_max_tokens: int = 1024,
    rerank_max_tokens: int = 1024,
) -> OnnxEngine:
    config = EngineConfig(
        models_dir=models_dir,
        batch_size=batch_size,
        embed_max_tokens=embed_max_tokens,
        rerank_max_tokens=rerank_max_tokens,
        threads=1,
    )
    return OnnxEngine(config)


def test_labels_and_dimension(models_dir: Path) -> None:
    engine = _engine(models_dir)
    assert engine.embed_model == "tiny/embed@onnx-test"
    assert engine.rerank_model == "tiny/rerank@onnx-test"
    assert engine.dim == DIM


def test_embeddings_are_normalised_and_independent_of_batching(models_dir: Path) -> None:
    texts = ["water", "girls school التعليم 2021 budget", "المياه points", "water"]
    batched = _engine(models_dir, batch_size=2).embed(texts)
    single = np.stack([_engine(models_dir, batch_size=1).embed([t])[0] for t in texts])
    assert batched.shape == (4, DIM)
    np.testing.assert_allclose(np.linalg.norm(batched, axis=1), 1.0, rtol=1e-5)
    np.testing.assert_allclose(batched, single, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(batched[0], batched[3], rtol=1e-6)


def test_embed_nothing(models_dir: Path) -> None:
    assert _engine(models_dir).embed([]).shape == (0, DIM)


def test_rerank_is_a_sigmoid_score_in_input_order(models_dir: Path) -> None:
    passages = ["budget", "water points", "school", "water"]
    scores = _engine(models_dir, batch_size=3).rerank("girls", passages)
    expected = [1 / (1 + np.exp(-x)) for x in (-3.0, 3.0, 0.0, 2.0)]
    np.testing.assert_allclose(scores, expected, rtol=1e-5)
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert _engine(models_dir).rerank("girls", []) == []


def test_token_counts_exclude_special_tokens_and_never_truncate(models_dir: Path) -> None:
    engine = _engine(models_dir, embed_max_tokens=4)
    long_text = " ".join(["water"] * 20)
    assert engine.count_tokens(["water points", "", long_text]) == [2, 0, 20]


def test_long_inputs_are_truncated_not_rejected(models_dir: Path) -> None:
    engine = _engine(models_dir, embed_max_tokens=4, rerank_max_tokens=6)
    long_text = " ".join(["girls"] * 50)
    assert engine.embed([long_text]).shape == (1, DIM)
    assert len(engine.rerank("water", [long_text])) == 1
