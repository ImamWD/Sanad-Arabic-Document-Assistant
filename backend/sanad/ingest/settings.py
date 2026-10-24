"""Ingestion settings, read from the environment (documented in .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from sanad.ingest.chunk import ChunkParams


class IngestSettings(BaseSettings):
    """Every field maps to an upper-case environment variable of the same name."""

    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    # Storage: originals and PDF renditions, on the `files` volume shared by api and worker.
    files_dir: Path = Path("/data/files")
    upload_max_bytes: int = Field(default=50 * 1024 * 1024, gt=0)

    # Chunking (DECISIONS D1), in bge-m3 tokens.
    chunk_target_tokens: int = Field(default=350, gt=0)
    chunk_max_tokens: int = Field(default=512, gt=0)
    chunk_overlap_tokens: int = Field(default=50, ge=0)
    chunk_min_tail_tokens: int = Field(default=80, ge=0)

    # NO_TEXT_LAYER: a page with fewer than `ingest_min_page_chars` characters of text but an
    # image on it is a scanned page; a document fails when more than
    # `ingest_scanned_page_share` of its pages are scanned.
    ingest_min_page_chars: int = Field(default=20, ge=1)
    ingest_scanned_page_share: float = Field(default=0.5, ge=0, le=1)

    libreoffice_timeout_seconds: float = Field(default=180, gt=0)

    # Worker: a claimed document whose stage hasn't moved for this long is stale (its worker
    # died); it is re-queued until it has been tried `worker_max_attempts` times.
    worker_stale_seconds: float = Field(default=900, gt=0)
    worker_max_attempts: int = Field(default=3, ge=1)

    # ml service calls.
    embed_batch_size: int = Field(default=8, ge=1, le=256)
    ml_timeout_seconds: float = Field(default=300, gt=0)

    # Seed corpus (registered by `python -m sanad.init`): manifest + rendered files.
    seed_dir: Path = Path("/app/seed")

    @property
    def chunk_params(self) -> ChunkParams:
        return ChunkParams(
            target_tokens=self.chunk_target_tokens,
            max_tokens=self.chunk_max_tokens,
            overlap_tokens=self.chunk_overlap_tokens,
            min_tail_tokens=self.chunk_min_tail_tokens,
        )


@lru_cache
def get_ingest_settings() -> IngestSettings:
    return IngestSettings()
