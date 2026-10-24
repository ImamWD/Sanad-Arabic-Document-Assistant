"""Claude through the official `anthropic` SDK. Optional and unused by default: hosted, so it
only ever receives synthetic seed excerpts (see base.py), behind docker-compose.api-llm.yml.

- No `temperature`, `top_p` or `top_k`: the API rejects them (CLAUDE.md, Environment).
- Thinking is left at the model's default (adaptive) with effort `medium`, set explicitly.
  `max_tokens` leaves room for thinking, which counts toward it.
- Server-side fallbacks are on (`fallbacks: "default"`): a declined request is retried on the
  model Anthropic recommends for that category. If the whole chain declines (`refusal`), the
  answer is treated like the sentinel and the user sees a refusal.
"""

import logging
from collections.abc import AsyncIterator

import anthropic

from sanad.llm.base import Delta, Done, HostedProvider, LlmUnavailableError, Stopwatch, TextDelta
from sanad.llm.prompts import Prompt

logger = logging.getLogger(__name__)

MAX_TOKENS = 16000
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(HostedProvider):
    name = "anthropic"

    def __init__(self, model: str, *, client: anthropic.AsyncAnthropic) -> None:
        super().__init__(model)
        self._client = client

    async def aclose(self) -> None:
        await self._client.close()

    async def _stream(self, prompt: Prompt) -> AsyncIterator[Delta]:
        watch = Stopwatch()
        try:
            async with self._client.beta.messages.stream(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=prompt.system,
                messages=[{"role": "user", "content": prompt.user}],
                output_config={"effort": "medium"},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            ) as stream:
                async for text in stream.text_stream:
                    if text:
                        watch.text_arrived()
                        yield TextDelta(text)
                final = await stream.get_final_message()
        except anthropic.APIStatusError as exc:
            raise LlmUnavailableError(f"anthropic answered {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise LlmUnavailableError(f"anthropic: {type(exc).__name__}") from exc
        except anthropic.AnthropicError as exc:  # credentials, response validation
            raise LlmUnavailableError(f"anthropic: {type(exc).__name__}") from exc
        prompt_ms, output_ms = watch.split_ms()
        refused = final.stop_reason == "refusal"
        if refused:
            logger.info("anthropic declined the request (stop_reason=refusal)")
        yield Done(
            prompt_tokens=final.usage.input_tokens,
            completion_tokens=final.usage.output_tokens,
            prompt_ms=prompt_ms,
            output_ms=output_ms,
            refused=refused,
        )
