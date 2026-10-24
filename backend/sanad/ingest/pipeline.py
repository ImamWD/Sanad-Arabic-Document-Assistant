"""The ingestion stages that touch files and the ml service, but not the database
(SYSTEM_DESIGN §5.2 steps 2-8). The worker wraps them in claims and transactions.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sanad.documents.models import DocLanguage
from sanad.documents.storage import rendition_path, resolve
from sanad.ingest.chunk import Chunk, chunk_document
from sanad.ingest.convert import to_pdf
from sanad.ingest.extract import check_text_layer, extract_pages
from sanad.ingest.filetypes import FileType, check_content
from sanad.ingest.ml_client import MlService
from sanad.ingest.settings import IngestSettings
from sanad.text.arabic import clean_extracted, detect_language


@dataclass(frozen=True)
class Extracted:
    viewer_path: str  # relative to FILES_DIR
    pages: list[str]  # cleaned text of every viewer page, page 1 first
    language: DocLanguage


@dataclass(frozen=True)
class Indexed:
    chunks: list[Chunk]
    vectors: list[list[float]]
    model: str


def extract_document(
    document_id: uuid.UUID, file_path: str, file_type: FileType, settings: IngestSettings
) -> Extracted:
    """Original file -> viewer PDF -> cleaned per-page text, or an IngestionError."""
    files_dir: Path = settings.files_dir
    original = resolve(files_dir, file_path)
    check_content(original, file_type)
    if file_type is FileType.PDF:
        viewer = file_path
    else:
        viewer = rendition_path(document_id)
        to_pdf(
            original, file_type, resolve(files_dir, viewer), settings.libreoffice_timeout_seconds
        )
    raw = extract_pages(resolve(files_dir, viewer), settings.pdf_extractor)
    pages = clean_extracted([page.text for page in raw])
    check_text_layer(pages, raw, settings.ingest_min_page_chars, settings.ingest_scanned_page_share)
    language = DocLanguage(detect_language("\n".join(pages)))
    return Extracted(viewer_path=viewer, pages=pages, language=language)


def index_pages(
    pages: list[str],
    ml: MlService,
    settings: IngestSettings,
    heartbeat: Callable[[], None] = lambda: None,
) -> Indexed:
    """Cleaned pages -> D1 chunks -> bge-m3 vectors."""
    chunks = chunk_document(pages, ml.count_tokens, settings.chunk_params)
    model, vectors = ml.embed([c.text for c in chunks], heartbeat)
    return Indexed(chunks=chunks, vectors=vectors, model=model)
