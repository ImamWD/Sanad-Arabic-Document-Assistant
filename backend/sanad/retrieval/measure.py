"""Measure retrieval on the running stack: recall@K of the dev questions' expected pages, and
where one chunk ranks for one question. Read-only; runs in backend-dev on the stack's network:

    docker compose run --rm backend-dev python -m sanad.retrieval.measure [--k 10]

It calls the same retriever that fills POST /ask's diagnostics (dense, lexical, RRF, rerank),
as the demo editor, but skips generation, so a pass over the 30 dev questions takes minutes
rather than half an hour. Prints JSON lines, then a summary.
"""

import argparse
import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any

import httpx2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from sanad.core.config import get_settings
from sanad.core.db import create_engine, create_sync_engine
from sanad.core.models import User
from sanad.documents.models import Chunk, Document
from sanad.retrieval.fuse import rrf
from sanad.retrieval.ml import AskMlClient
from sanad.retrieval.search import SqlRetriever, dense_ids, lexical_ids
from sanad.retrieval.settings import RetrievalSettings
from sanad.retrieval.types import Filters

REPO = Path(__file__).resolve().parents[3]
WLP_QUESTION = (
    "كم خُصّص لرواتب فريق المشروع في اتفاقية تمويل برنامج سبل العيش للنساء المعيلات لعام 2022؟"
)


def emit(row: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(row, ensure_ascii=False) + "\n")


async def main(k: int) -> None:
    settings = get_settings()
    rs = RetrievalSettings()
    with Session(create_sync_engine(settings), expire_on_commit=False) as db:
        editor = db.scalar(select(User).where(User.email == "editor@sanad.example"))
        wlp_chunk = db.scalar(
            select(Chunk.id)
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.original_filename == "wlp-donor-agreement-2022.pdf")
            .where(Chunk.text.contains("84,000"))
        )
        stamp = db.scalar(select(Chunk.embedding_model).limit(1))
    if editor is None or wlp_chunk is None:
        raise SystemExit("needs the seed corpus and the demo editor (make up)")
    yaml = importlib.import_module("yaml")  # a dev dependency: backend-dev has it
    questions = yaml.safe_load((REPO / "eval" / "dev_questions.yaml").read_text("utf-8"))
    engine = create_engine(settings)
    hits = answerable = 0
    async with httpx2.AsyncClient() as http:
        ml = AskMlClient(http, settings.ml_base_url, rs.ask_ml_timeout_seconds)
        retriever = SqlRetriever(engine, ml, rs)
        for item in questions["questions"]:
            result = await retriever.retrieve(editor, item["question"], Filters())
            top = [(c.file, c.page_number) for c in result.candidates[:k]]
            expected = {(e["file"], e["page"]) for e in item.get("expected_citations") or []}
            hit = bool(expected & set(top)) if expected else None
            if expected:
                answerable += 1
                hits += bool(hit)
            row: dict[str, Any] = {
                "id": item["id"],
                "hit": hit,
                "top_score": round(result.top_score or 0.0, 3),
            }
            emit(row)
        async with AsyncSession(engine) as db:
            vector = await ml.embed(WLP_QUESTION)
            dense = await dense_ids(db, editor, Filters(), vector, 200)
            lexical = await lexical_ids(db, editor, Filters(), WLP_QUESTION, 200)
        fused = rrf(
            [dense[: rs.dense_candidates], lexical[: rs.lexical_candidates]],
            k=rs.rrf_k,
            limit=rs.rerank_candidates,
        )
        wlp = await retriever.retrieve(editor, WLP_QUESTION, Filters())
    await engine.dispose()
    reranked = [c.chunk_id for c in wlp.candidates]
    emit(
        {
            "embedding_model": stamp,
            f"recall_at_{k}": f"{hits}/{answerable}",
            "wlp_dense_rank": dense.index(wlp_chunk) + 1,
            "wlp_lexical_rank": lexical.index(wlp_chunk) + 1 if wlp_chunk in lexical else None,
            "wlp_fused_rank": fused.index(wlp_chunk) + 1 if wlp_chunk in fused else None,
            "wlp_reranked_rank": reranked.index(wlp_chunk) + 1 if wlp_chunk in reranked else None,
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=10)
    asyncio.run(main(parser.parse_args().k))
