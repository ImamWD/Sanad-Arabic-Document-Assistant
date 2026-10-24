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
and onnxruntime has no fast fp16 kernels on CPU. int8 weights (dynamic quantisation for the
MatMuls, per-row int8 for the word embeddings) shrink each model from ~2.2 GB to ~0.6 GB,
and the client's Xeon (Cascade Lake, AVX-512 VNNI) runs int8 matrix products natively.

Each step runs in its own process, so the memory torch holds after exporting is returned to
the system before the quantiser loads the 2.2 GB fp32 graph.
"""

# ruff: noqa: T201, S603  -- build script: progress goes to the build log; runs itself.
from __future__ import annotations

import gc
import json
import os
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
# Largest |int8| a MatMul weight may take. 127 uses the full range; 63 (7 bits) can't
# saturate the 16-bit pairwise sums of onnxruntime's x86 int8 kernel on CPUs without VNNI.
WEIGHT_MAX = int(os.environ.get("QUANT_WEIGHT_MAX", "127"))
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
    """Rewrite the fp32 graph with int8 weights, in one pass, one weight at a time.

    onnxruntime's own quantiser keeps several full copies of a 2.2 GB graph (shape inference,
    reloads, float64 temporaries) and runs out of memory in 8 GB, so this does the same
    rewrite directly:

    - every MatMul with a constant 2-D weight (the Linear layers): the weight becomes int8
      with one symmetric scale per output column, and the activation is quantised on the
      fly. This is the node pattern onnxruntime's dynamic quantiser emits, which its graph
      optimiser fuses into a single integer MatMul at load time:
          DynamicQuantizeLinear(x) -> MatMulInteger -> Cast -> Mul(x_scale * w_scale)
    - the word-embedding table (250k x 1024): int8 with one scale per token row:
          Gather(int8 table, ids) -> Cast -> Mul(Gather(row scales, ids))

    Attention's activation-by-activation MatMuls, LayerNorm and biases stay fp32.
    """
    import numpy as np
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    model = onnx.load(str(work / "fp32.onnx"))  # loads the external weight files too
    graph = model.graph
    inits = {i.name: i for i in graph.initializer}
    uses: dict[str, int] = {}
    for node in graph.node:
        for name in node.input:
            uses[name] = uses.get(name, 0) + 1

    def take(name: str) -> np.ndarray:
        array = numpy_helper.to_array(inits[name]).astype(np.float32, copy=False)
        graph.initializer.remove(inits.pop(name))
        return array

    def add(array: np.ndarray, name: str) -> str:
        graph.initializer.append(numpy_helper.from_array(array, name))
        return name

    nodes: list[onnx.NodeProto] = []
    dynamic: dict[str, tuple[str, str, str]] = {}  # activation -> (x_q, x_scale, x_zero_point)
    matmuls = embeddings = 0
    for node in graph.node:
        weight = node.input[1] if len(node.input) > 1 else ""
        if (
            node.op_type == "MatMul"
            and weight in inits
            and len(inits[weight].dims) == 2
            and uses[weight] == 1
        ):
            w = take(weight)
            scale = np.abs(w).max(axis=0) / WEIGHT_MAX
            scale[scale == 0] = 1.0
            w_q = np.clip(np.rint(w / scale), -WEIGHT_MAX, WEIGHT_MAX).astype(np.int8)
            del w
            add(w_q, f"{weight}_quantized")
            add(scale.astype(np.float32), f"{weight}_scale")
            add(np.zeros(w_q.shape[1], dtype=np.int8), f"{weight}_zero_point")
            x = node.input[0]
            if x not in dynamic:
                dynamic[x] = (f"{x}_quantized", f"{x}_scale", f"{x}_zero_point")
                nodes.append(helper.make_node("DynamicQuantizeLinear", [x], list(dynamic[x])))
            x_q, x_scale, x_zero = dynamic[x]
            out = node.output[0]
            nodes += [
                helper.make_node(
                    "MatMulInteger",
                    [x_q, f"{weight}_quantized", x_zero, f"{weight}_zero_point"],
                    [f"{out}_int32"],
                ),
                helper.make_node("Mul", [x_scale, f"{weight}_scale"], [f"{out}_scale"]),
                helper.make_node("Cast", [f"{out}_int32"], [f"{out}_float"], to=TensorProto.FLOAT),
                helper.make_node("Mul", [f"{out}_float", f"{out}_scale"], [out]),
            ]
            matmuls += 1
        elif (
            node.op_type == "Gather"
            and node.input[1] == "input_ids"
            and node.input[0] in inits
            and len(inits[node.input[0]].dims) == 2
            and inits[node.input[0]].dims[0] > 100_000
        ):
            table_name = node.input[0]
            table = take(table_name)
            rows = (np.abs(table).max(axis=1) / 127.0).astype(np.float32)
            rows[rows == 0] = 1.0
            table_q = np.empty(table.shape, dtype=np.int8)
            for start in range(0, table.shape[0], 8192):
                part = slice(start, start + 8192)
                table_q[part] = np.clip(np.rint(table[part] / rows[part, None]), -127, 127)
            del table
            add(table_q, f"{table_name}_quantized")
            add(rows, f"{table_name}_row_scale")
            add(np.array([-1], dtype=np.int64), f"{table_name}_last_axis")
            out = node.output[0]
            nodes += [
                helper.make_node("Gather", [f"{table_name}_quantized", "input_ids"], [f"{out}_q"]),
                helper.make_node("Cast", [f"{out}_q"], [f"{out}_float"], to=TensorProto.FLOAT),
                helper.make_node("Gather", [f"{table_name}_row_scale", "input_ids"], [f"{out}_s"]),
                helper.make_node(
                    "Unsqueeze", [f"{out}_s", f"{table_name}_last_axis"], [f"{out}_scale"]
                ),
                helper.make_node("Mul", [f"{out}_float", f"{out}_scale"], [out]),
            ]
            embeddings += 1
        else:
            nodes.append(node)
    if matmuls == 0 or embeddings != 1:
        raise SystemExit(f"unexpected graph: {matmuls} weight MatMuls, {embeddings} embeddings")
    del graph.node[:]
    graph.node.extend(nodes)
    onnx.checker.check_model(model)
    onnx.save(model, str(work / "model.onnx"))
    print(f"quantised {matmuls} MatMul weights and the word embeddings to int8", flush=True)


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
    """Compare int8 onnxruntime with fp32 torch; record the agreement in model.json.

    The service runs one text at a time (ML_BATCH_SIZE=1), because activations are quantised
    with one scale per tensor: in a padded batch a text's result depends on its neighbours.
    So the gate is on single-text results; the batch effect is recorded for information.
    """
    import numpy as np
    import onnxruntime as ort
    import torch

    items: list[str] | list[tuple[str, str]]
    items = CHECK_TEXTS if spec.slot == "embed" else [(CHECK_QUERY, p) for p in CHECK_PASSAGES]
    ids, mask = _encode(work / "tokenizer.json", items)
    session = ort.InferenceSession(str(work / "model.onnx"), providers=["CPUExecutionProvider"])
    batched = session.run([spec.output], {"input_ids": ids, "attention_mask": mask})[0]
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

        def unit(x: np.ndarray) -> np.ndarray:
            return x / np.linalg.norm(x, axis=1, keepdims=True)

        cosine = (unit(single) * unit(fp32)).sum(axis=1)
        batch_effect = (unit(single) * unit(batched)).sum(axis=1)
        info = {
            "dim": int(fp32.shape[1]),
            "check_min_cosine_vs_fp32": round(float(cosine.min()), 4),
            "check_mean_cosine_vs_fp32": round(float(cosine.mean()), 4),
            "info_min_cosine_single_vs_padded_batch": round(float(batch_effect.min()), 4),
        }
        ok = cosine.min() >= MIN_COSINE
    else:
        s8, s32, sb = (1 / (1 + np.exp(-x.astype(np.float64))) for x in (single, fp32, batched))
        info = {
            "dim": None,
            "check_max_score_diff_vs_fp32": round(float(np.abs(s8 - s32).max()), 4),
            "check_same_top_passage_as_fp32": int(np.argmax(s8)) == int(np.argmax(s32)),
            "check_scores_int8": [round(float(s), 4) for s in s8],
            "check_scores_fp32": [round(float(s), 4) for s in s32],
            "info_max_score_diff_single_vs_padded_batch": round(float(np.abs(s8 - sb).max()), 4),
        }
        ok = (
            np.abs(s8 - s32).max() <= MAX_SCORE_DIFF
            # An answer passage (Arabic or English) comes first, the same one in both.
            and int(np.argmax(s8)) == int(np.argmax(s32))
            and int(np.argmax(s8)) in {0, 2}
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
