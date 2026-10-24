"""Build-time only: download the pinned BAAI models, export them to ONNX, quantise to int8.

    python ml/build/export_models.py /opt/models

Runs in the `models` stage of ml/Dockerfile, on the build machine's own architecture: an
ONNX graph is plain data, so the result is the same for amd64 and arm64 images and torch
never runs under emulation. The runtime image receives only, per model:

    <out>/<embed|rerank>/model.onnx      int8 graph (dynamic quantisation)
    <out>/<embed|rerank>/tokenizer.json  the model's own tokenizer
    <out>/<embed|rerank>/model.json      repo id, pinned revision, variant, output name

Why int8: the whole stack has to fit in about 8 GB of Docker memory on a reviewer's laptop,
and onnxruntime has no fast fp16 kernels on CPU. Dynamic int8 quantisation shrinks each
model from ~2.2 GB to ~0.6 GB, and the client's Xeon (Cascade Lake, AVX-512 VNNI) runs
int8 matrix products natively.
"""

# ruff: noqa: T201  -- build script: progress goes to the build log.
from __future__ import annotations

import gc
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import torch
from huggingface_hub import snapshot_download
from onnxruntime.quantization import QuantType, quantize_dynamic
from transformers import AutoModel, AutoModelForSequenceClassification

OPSET = 17
VARIANT = "onnx-int8"


@dataclass(frozen=True)
class Spec:
    slot: str  # directory under <out>
    repo: str
    revision: str  # pinned commit: the weights never change under us
    output: str


EMBED = Spec("embed", "BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181", "embedding")
RERANK = Spec(
    "rerank", "BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e", "logit"
)


class CLSEmbedding(torch.nn.Module):
    """bge-m3 dense embedding: the normalised hidden state of the first (CLS) token."""

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        hidden = self.model(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        return torch.nn.functional.normalize(hidden[:, 0], dim=-1)


class RelevanceLogit(torch.nn.Module):
    """bge-reranker-v2-m3: one relevance logit per (query, passage) pair."""

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        return self.model(input_ids=input_ids, attention_mask=attention_mask).logits[:, 0]


def download(spec: Spec) -> Path:
    patterns = ["config.json", "tokenizer.json", "*.safetensors"]
    path = Path(snapshot_download(spec.repo, revision=spec.revision, allow_patterns=patterns))
    if not any(path.glob("*.safetensors")):
        # bge-m3 publishes pytorch_model.bin only.
        patterns = ["config.json", "tokenizer.json", "pytorch_model.bin"]
        path = Path(snapshot_download(spec.repo, revision=spec.revision, allow_patterns=patterns))
    return path


def export(spec: Spec, out: Path) -> None:
    print(f"[{spec.slot}] {spec.repo}@{spec.revision}", flush=True)
    src = download(spec)
    if spec.slot == "embed":
        wrapper: torch.nn.Module = CLSEmbedding(AutoModel.from_pretrained(src))
    else:
        wrapper = RelevanceLogit(AutoModelForSequenceClassification.from_pretrained(src))
    wrapper.eval()

    target = out / spec.slot
    target.mkdir(parents=True, exist_ok=True)
    # Dummy input: <s> x x x </s>. Batch and sequence axes are dynamic.
    ids = torch.tensor([[0, 1000, 1001, 1002, 2], [0, 1003, 2, 1, 1]], dtype=torch.long)
    mask = (ids != 1).long()
    with tempfile.TemporaryDirectory() as tmp:
        fp32 = Path(tmp) / "model.onnx"
        with torch.inference_mode():
            torch.onnx.export(
                wrapper,
                (ids, mask),
                str(fp32),
                input_names=["input_ids", "attention_mask"],
                output_names=[spec.output],
                dynamic_axes={
                    "input_ids": {0: "batch", 1: "sequence"},
                    "attention_mask": {0: "batch", 1: "sequence"},
                    spec.output: {0: "batch"},
                },
                opset_version=OPSET,
                dynamo=False,
            )
            dim = int(wrapper(ids, mask).shape[-1]) if spec.slot == "embed" else None
        del wrapper
        gc.collect()
        print(f"[{spec.slot}] quantising to int8", flush=True)
        quantize_dynamic(
            fp32,
            target / "model.onnx",
            weight_type=QuantType.QInt8,
            per_channel=True,
            use_external_data_format=False,
        )
    shutil.copyfile(src / "tokenizer.json", target / "tokenizer.json")
    info = {
        "name": spec.repo,
        "revision": spec.revision,
        "variant": VARIANT,
        "output": spec.output,
        "dim": dim,
    }
    (target / "model.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    size_mb = (target / "model.onnx").stat().st_size / 2**20
    print(f"[{spec.slot}] done: {size_mb:.0f} MiB", flush=True)


def main() -> None:
    out = Path(sys.argv[1])
    torch.set_num_threads(max(1, torch.get_num_threads()))
    for spec in (EMBED, RERANK):
        export(spec, out)
        gc.collect()


if __name__ == "__main__":
    main()
