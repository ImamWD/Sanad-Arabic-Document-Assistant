"""Build the configured provider (LLM_PROVIDER). ollama unless deliberately overridden."""

import anthropic

from sanad.llm.anthropic import AnthropicProvider
from sanad.llm.base import LlmProvider
from sanad.llm.ollama import OllamaProvider
from sanad.llm.openai_compat import OpenAICompatProvider
from sanad.llm.settings import DEFAULT_ANTHROPIC_MODEL, DEFAULT_OLLAMA_MODEL, LlmSettings


class ProviderConfigError(Exception):
    """LLM_PROVIDER needs a setting that isn't there."""


def build_provider(settings: LlmSettings) -> LlmProvider:
    match settings.llm_provider:
        case "ollama":
            return OllamaProvider(
                settings.llm_model or DEFAULT_OLLAMA_MODEL,
                base_url=settings.ollama_base_url,
                num_ctx=settings.ollama_num_ctx,
                max_output_tokens=settings.llm_max_output_tokens,
                keep_alive=settings.ollama_keep_alive,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        case "openai_compat":
            if not settings.llm_model or not settings.openai_compat_base_url:
                raise ProviderConfigError(
                    "openai_compat needs LLM_MODEL and OPENAI_COMPAT_BASE_URL"
                )
            key = settings.openai_compat_api_key
            return OpenAICompatProvider(
                settings.llm_model,
                base_url=settings.openai_compat_base_url,
                api_key=key.get_secret_value() if key else None,
                max_output_tokens=settings.llm_max_output_tokens,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        case "anthropic":
            key = settings.anthropic_api_key
            client = anthropic.AsyncAnthropic(
                api_key=key.get_secret_value() if key else None,
                timeout=settings.llm_timeout_seconds,
            )
            return AnthropicProvider(settings.llm_model or DEFAULT_ANTHROPIC_MODEL, client=client)
