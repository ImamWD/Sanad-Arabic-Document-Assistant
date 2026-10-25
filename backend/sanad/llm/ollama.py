"""Ollama, the shipped default provider: local generation on the internal network only.

Per S3's notes: `num_ctx` is always sent (Ollama's default silently truncates the prompt),
`think` is off, and temperature is 0 so the same question gets the same answer.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx2

from sanad.llm.base import Delta, Done, LlmProvider, LlmUnavailableError, Stopwatch, TextDelta
from sanad.llm.prompts import Prompt


class OllamaProvider(LlmProvider):
    name = "ollama"

    def __init__(
        self,
        model: str,
        *,
        base_url: str,
        num_ctx: int,
        max_output_tokens: int,
        keep_alive: str,
        timeout_seconds: float,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(model)
        self._num_ctx = num_ctx
        self._max_output_tokens = max_output_tokens
        self._keep_alive = keep_alive
        self._client = httpx2.AsyncClient(
            base_url=base_url,
            timeout=httpx2.Timeout(timeout_seconds, connect=10.0),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _body(self, prompt: Prompt) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "stream": True,
            "think": False,
            "keep_alive": self._keep_alive,
            "options": {
                "temperature": 0,
                "num_ctx": self._num_ctx,
                "num_predict": self._max_output_tokens,
            },
        }

    async def stream(self, prompt: Prompt) -> AsyncIterator[Delta]:
        watch = Stopwatch()
        try:
            async with self._client.stream("POST", "/api/chat", json=self._body(prompt)) as resp:
                if resp.status_code != 200:
                    await resp.aread()
                    raise LlmUnavailableError(f"ollama answered {resp.status_code}")
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if "error" in chunk:
                        raise LlmUnavailableError("ollama reported an error mid-stream")
                    text = chunk.get("message", {}).get("content") or ""
                    if text:
                        watch.text_arrived()
                        yield TextDelta(text)
                    if chunk.get("done"):
                        prompt_ms, output_ms = watch.split_ms()
                        yield Done(
                            prompt_tokens=chunk.get("prompt_eval_count"),
                            completion_tokens=chunk.get("eval_count"),
                            prompt_ms=prompt_ms,
                            output_ms=output_ms,
                        )
                        return
        except (httpx2.HTTPError, ValueError) as exc:
            raise LlmUnavailableError(f"ollama: {type(exc).__name__}") from exc
        raise LlmUnavailableError("ollama stream ended without done")
