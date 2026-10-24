"""Retrieval and gate settings, read from the environment (documented in .env.example)."""

from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrievalSettings(BaseSettings):
    """Every field maps to an upper-case environment variable of the same name."""

    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    # The three-band gate (DECISIONS D4) on the reranker's top score (0..1, int8 bge-reranker):
    # below T_REFUSE the LLM is not called; below T_CONFIDENT the answer gets the amber banner.
    # Provisional until E2 tunes both on the dev set.
    t_refuse: float = Field(default=0.15, ge=0, le=1)
    t_confident: float = Field(default=0.5, ge=0, le=1)

    dense_candidates: int = Field(default=40, ge=1)
    lexical_candidates: int = Field(default=40, ge=1)
    rrf_k: int = Field(default=60, ge=1)
    # Fused candidates sent to the reranker. On CPU each costs about as much as embedding it.
    rerank_candidates: int = Field(default=30, ge=1)
    # Excerpts sent to the LLM, best reranked first.
    retrieval_top_k: int = Field(default=6, ge=1)
    # "You may want to check" titles on a refusal.
    nearest_documents: int = Field(default=3, ge=0)
    snippet_chars: int = Field(default=300, ge=40)
    question_max_chars: int = Field(default=1000, ge=10)
    ask_ml_timeout_seconds: float = Field(default=120, gt=0)

    @model_validator(mode="after")
    def _ordered_thresholds(self) -> Self:
        if self.t_refuse > self.t_confident:
            raise ValueError("T_REFUSE must not exceed T_CONFIDENT")
        return self


@lru_cache
def get_retrieval_settings() -> RetrievalSettings:
    return RetrievalSettings()
