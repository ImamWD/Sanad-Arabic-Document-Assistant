"""The running stack (`make up`): the seed corpus as the worker really ingested it.

- every seed document reaches `ready` on first boot
- every chunk sits on the page of the viewer PDF it names (checked against the PDF the API
  serves), and every eval fact is found in a chunk of its cited page
- a viewer can neither list nor open a restricted document; the guest sees seed documents only

Talks to the stack's api over the backend network and reads its database; changes nothing.
Skipped with a reason when the stack isn't running.
"""

import re
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
import sqlalchemy
from sqlalchemy import select, text

from sanad.core.config import get_settings
from sanad.documents.models import Chunk, DocStatus, Document
from sanad.ingest.extract import extract_pages
from sanad.text.arabic import clean_extracted, normalize_for_search
from tests.ingest.conftest import REPO, SEED_ENTRIES, needs_seed_files

API = "http://api:8000/api"
CSRF = {"X-Sanad": "1"}
READY_TIMEOUT_SECONDS = 1200


def _stack_is_up() -> bool:
    try:
        return httpx2.get(f"{API}/health", timeout=3).status_code == 200
    except httpx2.HTTPError:
        return False


pytestmark = [
    pytest.mark.skipif(not _stack_is_up(), reason="the stack isn't running (make up)"),
    needs_seed_files,
]


@pytest.fixture(scope="module")
def live_db() -> Iterator[sqlalchemy.Engine]:
    """The stack's own database (read only)."""
    engine = sqlalchemy.create_engine(get_settings().database_url)
    yield engine
    engine.dispose()


def login(who: str) -> httpx2.Client:
    settings = get_settings()
    client = httpx2.Client(base_url=API, timeout=60, headers=CSRF)
    if who == "guest":
        response = client.post("/auth/guest", json={})
    else:
        password = getattr(settings, f"demo_{who}_password").get_secret_value()
        response = client.post(
            "/auth/login", json={"email": f"{who}@sanad.example", "password": password}
        )
    assert response.status_code == 200, response.text
    return client


@pytest.fixture(scope="module")
def ready_seed(live_db: sqlalchemy.Engine) -> dict[str, Document]:
    """Wait for the worker to finish the seed corpus; the seed documents by file name."""
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while True:
        with live_db.connect() as conn:
            rows = {
                r.original_filename: r
                for r in conn.execute(select(Document).where(Document.is_seed.is_(True)))
            }
        busy = [r for r in rows.values() if r.status not in (DocStatus.READY, DocStatus.FAILED)]
        if len(rows) == len(SEED_ENTRIES) and not busy:
            return rows  # type: ignore[return-value]
        if time.monotonic() > deadline:
            pytest.fail(
                f"seed corpus not ingested in time: {len(rows)} registered, {len(busy)} busy"
            )
        time.sleep(5)


def test_the_seed_corpus_reaches_ready_on_first_boot(ready_seed: dict[str, Any]) -> None:
    failed = {name: row.error_code for name, row in ready_seed.items() if row.status != "ready"}
    assert failed == {}
    for entry in SEED_ENTRIES:
        row = ready_seed[entry["file"]]
        assert row.page_count == entry["page_count"], entry["file"]
        assert row.restricted is bool(entry.get("restricted", False))
        assert row.is_archived is bool(entry.get("archived", False))


def test_chunks_sit_on_the_viewer_pdf_page_they_name(
    ready_seed: dict[str, Any], live_db: sqlalchemy.Engine
) -> None:
    admin = login("admin")
    with live_db.connect() as conn, tempfile.TemporaryDirectory() as tmp:
        for entry in SEED_ENTRIES:
            row = ready_seed[entry["file"]]
            response = admin.get(f"/documents/{row.id}/file")
            assert response.status_code == 200, entry["file"]
            pdf = Path(tmp) / f"{row.id}.pdf"
            pdf.write_bytes(response.content)
            pages = clean_extracted([p.text for p in extract_pages(pdf)])
            assert len(pages) == entry["page_count"]
            chunks = conn.execute(
                select(Chunk.page_number, Chunk.text).where(Chunk.document_id == row.id)
            ).all()
            assert chunks, entry["file"]
            for chunk in chunks:
                assert chunk.text in pages[chunk.page_number - 1], (
                    entry["file"],
                    chunk.page_number,
                )


def _fact_on(fact: str, haystack: str) -> bool:
    needle = normalize_for_search(fact).strip()
    return re.search(rf"(?<![\w.,]){re.escape(needle)}(?![\w]|[.,]\d)", haystack) is not None


@pytest.mark.parametrize("questions", ["eval/questions.yaml", "eval/dev_questions.yaml"])
def test_every_eval_fact_is_in_a_chunk_of_its_cited_page(
    ready_seed: dict[str, Any], live_db: sqlalchemy.Engine, questions: str
) -> None:
    yaml = pytest.importorskip("yaml")
    items = yaml.safe_load((REPO / questions).read_text(encoding="utf-8"))["questions"]
    with live_db.connect() as conn:
        page_chunks: dict[tuple[str, int], str] = {}
        for name, row in ready_seed.items():
            for page, norm in conn.execute(
                text(
                    "SELECT page_number, string_agg(text_norm, ' ') FROM chunks"
                    " WHERE document_id = :id GROUP BY page_number"
                ),
                {"id": row.id},
            ):
                page_chunks[(name, page)] = norm
    missing = []
    for item in items:
        citations = [(c["file"], c["page"]) for c in item.get("expected_citations") or []]
        for fact in item.get("must_include") or []:
            found = [_fact_on(str(fact), page_chunks.get(c, "")) for c in citations]
            ok = any(found) if "cross_document" in item.get("kinds", []) else all(found)
            if not ok:
                missing.append((item["id"], fact))
    assert missing == []


def test_a_viewer_can_neither_list_nor_open_a_restricted_document(
    ready_seed: dict[str, Any],
) -> None:
    restricted = [row for row in ready_seed.values() if row.restricted]
    if not restricted:
        pytest.skip("seed/manifest.json marks no document restricted yet (C1b)")
    viewer = login("viewer")
    listed = viewer.get("/documents", params={"page_size": 100, "include_archived": True}).json()
    assert not any(item["restricted"] for item in listed["items"])
    for row in restricted:
        for suffix in ("", "/file", "/pages/1"):
            assert viewer.get(f"/documents/{row.id}{suffix}").status_code == 404
    editor = login("editor")
    assert editor.get(f"/documents/{restricted[0].id}").status_code == 200


def test_the_guest_sees_seed_documents_only(ready_seed: dict[str, Any]) -> None:
    guest = login("guest")
    listed = guest.get("/documents", params={"page_size": 100, "include_archived": True}).json()
    assert listed["items"]
    assert all(item["is_seed"] and not item["restricted"] for item in listed["items"])
    visible = sum(1 for row in ready_seed.values() if not row.restricted)
    assert listed["total"] == visible
