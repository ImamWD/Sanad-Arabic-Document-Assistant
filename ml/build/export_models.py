"""Build-time only: download the pinned BAAI models, export them to ONNX, quantise to int8,
and check the int8 graphs against the original fp32 PyTorch models.

    python ml/build/export_models.py /opt/models

Runs in the `models` stage of ml/Dockerfile, on the build machine's own architecture: an
ONNX graph is plain data, so the result is the same for amd64 and arm64 images and torch
never runs under emulation. The runtime image receives only, per model:

    <out>/<embed|rerank>/model.onnx      int8 graph (dynamic quantisation)
    <out>/<embed|rerank>/tokenizer.json  the model's own tokenizer
    <out>/<embed|rerank>/model.json      repo id, pinned revision, variant, output name,
                                         and the fp32-vs-int8 agreement measured here

Why int8: the whole stack has to fit in about 8 GB of Docker memory on a reviewer's laptop,
and onnxruntime has no fast fp16 kernels on CPU. Dynamic int8 quantisation shrinks each
model from ~2.2 GB to ~0.6 GB, and the client's Xeon (Cascade Lake, AVX-512 VNNI) runs int8
matrix products natively.

Each step runs in its own process, so the memory torch holds after exporting is returned to
the system before the quantiser loads the 2.2 GB fp32 graph.
"""

# ruff: noqa: T201, S603  -- build script: progress goes to the build log; it runs itself.
from __future__ import annotations

import gc
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

OPSET = 17
VARIANT = "onnx-int8"
# Synthetic, in the style of the seed corpus. Mixed lengths, so a batch needs padding.
CHECK_TEXTS = [
    "بلغ عدد المستفيدين من برنامج تمكين الشباب للتوظيف 1,250 شابًا وشابة في عام 2021.",
    "تم تمويل المشروع YEP-2021-03 عبر صندوق تلال العنبر للتنمية.",
    "The Foundation rehabilitated 42 rural water points in the Eastern Plateau in 2019.",
    "التعليــم",
    "نسبة التحاق الفتيات بالتعليم الأساسي ارتفعت إلى 87% في سهل القمر بعد توزيع الحقائب "
    "المدرسية وتدريب المعلمين وتحسين المرافق الصحية في المدارس المستهدفة خلال العام الدراسي.",
    "Board minutes, March 2023: the board approved the revised budget for the next year.",
]
CHECK_QUERY = "كم عدد نقاط المياه التي تم تأهيلها؟"
CHECK_PASSAGES = [
    "أعادت المؤسسة تأهيل 42 نقطة مياه ريفية في الهضبة الشرقية خلال عام 2019.",
    "ناقش مجلس الإدارة الميزانية المعدلة للعام المقبل ووافق عليها.",
    "The Foundation rehabilitated 42 rural water points in the Eastern Plateau in 2019.",
    "بلغ عدد المتطوعين 340 متطوعًا ومتطوعة.",
]
# Fail the build if quantisation broke the model, not merely if it nudged it.
MIN_COSINE = 0.95
MAX_SCORE_DIFF = 0.15


@dataclass(frozen=True)
class Spec:
    slot: str  # directory under <out>
    repo: str
    revision: str  # pinned commit: the weights never change under us
    output: str


SPECS = {
    "embed": Spec("embed", "BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181", "embedding"),
    "rerank": Spec(
        "rerank", "BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e", "logit"
    ),
}


def download(spec: Spec) -> Path:
    from huggingface_hub import snapshot_download

    for weights in ("*.safetensors", "pytorch_model.bin"):  # bge-m3 publishes .bin only
        path = Path(
            snapshot_download(
                spec.repo,
                revision=spec.revision,
                allow_patterns=["config.json", "tokenizer.json", weights],
            )
        )
        if any(path.glob(weights)):
            return path
    raise SystemExit(f"no weights found for {spec.repo}")


def load_torch(spec: Spec):  # returns (torch module, source dir); torch is build-only
    import torch
    from transformers import AutoModel, AutoModelForSequenceClassification

    class CLSEmbedding(torch.nn.Module):
        """bge-m3 dense embedding: the normalised hidden state of the first (CLS) token."""

        def __init__(self, model: torch.nn.Module) -> None:
            super().__init__()
            self.model = model

        def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
            out = self.model(input_ids=input_ids, attention_mask=attention_mask)
            return torch.nn.functional.normalize(out.last_hidden_state[:, 0], dim=-1)

    class RelevanceLogit(torch.nn.Module):
        """bge-reranker-v2-m3: one relevance logit per (query, passage) pair."""

        def __init__(self, model: torch.nn.Module) -> None:
            super().__init__()
            self.model = model

        def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
            return self.model(input_ids=input_ids, attention_mask=attention_mask).logits[:, 0]

    src = download(spec)
    if spec.slot == "embed":
        wrapper = CLSEmbedding(AutoModel.from_pretrained(src))
    else:
        wrapper = RelevanceLogit(AutoModelForSequenceClassification.from_pretrained(src))
    return wrapper.eval(), src


def step_export(spec: Spec, work: Path) -> None:
    import torch

    wrapper, src = load_torch(spec)
    # Dummy input: <s> x x x </s> and a padded row. Batch and sequence axes are dynamic.
    ids = torch.tensor([[0, 1000, 1001, 1002, 2], [0, 1003, 2, 1, 1]], dtype=torch.long)
    mask = (ids != 1).long()
    with torch.inference_mode():
        torch.onnx.export(
            wrapper,
            (ids, mask),
            str(work / "fp32.onnx"),
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
    shutil.copyfile(src / "tokenizer.json", work / "tokenizer.json")


def step_quantize(work: Path) -> None:
    from onnxruntime.quantization import QuantType, quantize_dynamic

    quantize_dynamic(
        work / "fp32.onnx",
        work / "model.onnx",
        weight_type=QuantType.QInt8,
        per_channel=True,
    )


def _encode(tokenizer_path: Path, items: list[str] | list[tuple[str, str]]):
    import numpy as np
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.enable_truncation(max_length=1024)
    encodings = tokenizer.encode_batch(items)
    width = max(len(e.ids) for e in encodings)
    ids = np.ones((len(encodings), width), dtype=np.int64)  # 1 = <pad>
    mask = np.zeros_like(ids)
    for row, e in enumerate(encodings):
        ids[row, : len(e.ids)] = e.ids
        mask[row, : len(e.ids)] = 1
    return ids, mask


def step_verify(spec: Spec, work: Path) -> None:
    """Compare int8 onnxruntime with fp32 torch on a padded batch; record the agreement."""
    import numpy as np
    import onnxruntime as ort
    import torch

    items: list[str] | list[tuple[str, str]]
    items = CHECK_TEXTS if spec.slot == "embed" else [(CHECK_QUERY, p) for p in CHECK_PASSAGES]
    ids, mask = _encode(work / "tokenizer.json", items)
    session = ort.InferenceSession(str(work / "model.onnx"), providers=["CPUExecutionProvider"])
    int8 = session.run([spec.output], {"input_ids": ids, "attention_mask": mask})[0]
    single = np.concatenate(
        [
            session.run(
                [spec.output],
                {
                    "input_ids": ids[i : i + 1, : mask[i].sum()],
                    "attention_mask": mask[i : i + 1, : mask[i].sum()],
                },
            )[0]
            for i in range(len(ids))
        ]
    )
    wrapper, _ = load_torch(spec)
    with torch.inference_mode():
        fp32 = wrapper(torch.from_numpy(ids), torch.from_numpy(mask)).numpy()
    del wrapper
    gc.collect()

    info: dict[str, object] = {}
    if spec.slot == "embed":
        unit = int8 / np.linalg.norm(int8, axis=1, keepdims=True)
        cosine = (unit * fp32).sum(axis=1)
        padding = (unit * (single / np.linalg.norm(single, axis=1, keepdims=True))).sum(axis=1)
        info = {
            "dim": int(fp32.shape[1]),
            "check_min_cosine_vs_fp32": round(float(cosine.min()), 4),
            "check_mean_cosine_vs_fp32": round(float(cosine.mean()), 4),
            "check_min_cosine_padded_vs_single": round(float(padding.min()), 4),
        }
        ok = cosine.min() >= MIN_COSINE and padding.min() >= 0.999
    else:
        s8, s32, s1 = (1 / (1 + np.exp(-x.astype(np.float64))) for x in (int8, fp32, single))
        info = {
            "dim": None,
            "check_max_score_diff_vs_fp32": round(float(np.abs(s8 - s32).max()), 4),
            "check_max_score_diff_padded_vs_single": round(float(np.abs(s8 - s1).max()), 4),
            "check_same_ranking_as_fp32": bool((np.argsort(-s8) == np.argsort(-s32)).all()),
            "check_scores_int8": [round(float(s), 4) for s in s8],
            "check_scores_fp32": [round(float(s), 4) for s in s32],
        }
        ok = (
            np.abs(s8 - s32).max() <= MAX_SCORE_DIFF
            and np.abs(s8 - s1).max() <= 1e-3
            # Either answer passage (Arabic or English) must come first, in both precisions.
            and int(np.argmax(s8)) in {0, 2}
            and int(np.argmax(s32)) in {0, 2}
        )
    print(f"[{spec.slot}] check: {json.dumps(info, ensure_ascii=False)}", flush=True)
    if not ok:
        raise SystemExit(f"[{spec.slot}] int8 model disagrees with fp32; refusing to ship it")
    (work / "check.json").write_text(json.dumps(info), encoding="utf-8")


def _run(*args: str) -> None:
    subprocess.run([sys.executable, __file__, *args], check=True)


def main() -> None:
    if sys.argv[1] == "--step":
        step, slot, work = sys.argv[2], sys.argv[3], Path(sys.argv[4])
        if step == "export":
            step_export(SPECS[slot], work)
        elif step == "quantize":
            step_quantize(work)
        else:
            step_verify(SPECS[slot], work)
        return

    out = Path(sys.argv[1])
    for slot, spec in SPECS.items():
        work = Path("/tmp/export") / slot  # noqa: S108 - a build container
        work.mkdir(parents=True, exist_ok=True)
        print(f"[{slot}] {spec.repo}@{spec.revision}: export", flush=True)
        _run("--step", "export", slot, str(work))
        print(f"[{slot}] quantise to int8", flush=True)
        _run("--step", "quantize", slot, str(work))
        for name in work.iterdir():  # free the fp32 graph and its external weights
            if name.name not in {"model.onnx", "tokenizer.json"}:
                name.unlink()
        print(f"[{slot}] verify against fp32", flush=True)
        _run("--step", "verify", slot, str(work))

        target = out / slot
        target.mkdir(parents=True, exist_ok=True)
        shutil.move(work / "model.onnx", target / "model.onnx")
        shutil.move(work / "tokenizer.json", target / "tokenizer.json")
        check = json.loads((work / "check.json").read_text(encoding="utf-8"))
        info = {
            "name": spec.repo,
            "revision": spec.revision,
            "variant": VARIANT,
            "output": spec.output,
            **check,
        }
        (target / "model.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        shutil.rmtree(work)
        size_mb = (target / "model.onnx").stat().st_size / 2**20
        print(f"[{slot}] done: {size_mb:.0f} MiB", flush=True)


if __name__ == "__main__":
    main()
