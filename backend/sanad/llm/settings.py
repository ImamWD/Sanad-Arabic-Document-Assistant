"""LLM settings, read from the environment (documented in .env.example)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["ollama", "openai_compat", "anthropic"]

# The shipped default model (S3, PR #5): gemma4:e4b-it-qat served text-only, with use_mmap and
# num_ctx 8192, so the whole stack fits ~8 GB of Docker memory. `ollama-init` builds it under
# this name from the pulled base model; docker-compose.yml uses the same names (a test checks).
DEFAULT_OLLAMA_MODEL = "sanad-gemma4-e4b-text"
OLLAMA_BASE_MODEL = "gemma4:e4b-it-qat"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"


class LlmSettings(BaseSettings):
    """Every field maps to an upper-case environment variable of the same name."""

    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    # ollama is the only provider used for real documents (DECISIONS D3). The hosted ones are
    # for benchmarks on the synthetic seed corpus, behind docker-compose.api-llm.yml.
    llm_provider: ProviderName = "ollama"
    # Unset: the provider's default (ollama: the S3 model; anthropic: claude-opus-5-5).
    # openai_compat has no default and needs it set.
    llm_model: str | None = None
    llm_max_output_tokens: int = Field(default=1024, gt=0)
    # Covers the longest wait for the first token: prompt processing on CPU produces nothing.
    llm_timeout_seconds: float = Field(default=600, gt=0)
    # Generations running at once. Waiting requests get a `queued` stage with their position.
    llm_max_concurrency: int = Field(default=1, ge=1)

    ollama_base_url: str = "http://ollama:11434"
    # Ollama's own default silently truncates a ~4k-token RAG prompt (S3), so always send this.
    ollama_num_ctx: int = Field(default=8192, ge=2048)
    ollama_keep_alive: str = "30m"

    openai_compat_base_url: str = ""
    openai_compat_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    # The answer-time estimate before this machine has measured any answers.
    eta_default_seconds: float = Field(default=60, gt=0)
    # Measured answers the estimate is based on (the most recent ones, for this model).
    eta_sample_count: int = Field(default=20, ge=1)
    # Fewer measured answers than this: the estimate is ETA_DEFAULT_SECONDS per generation.
    eta_min_samples: int = Field(default=5, ge=1)
    # The longest estimate shown; above it the stream says `capped` (the server is busy).
    eta_max_seconds: float = Field(default=600, gt=0)
    # SSE keep-alive: a `: ping` comment whenever no event was sent for this long.
    sse_ping_seconds: float = Field(default=15, gt=0)


@lru_cache
def get_llm_settings() -> LlmSettings:
    return LlmSettings()
