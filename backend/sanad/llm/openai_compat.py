"""Generic OpenAI-compatible chat completions: a free hosted reference model, or a vLLM or
llama.cpp host. Hosted, so it only ever receives synthetic seed excerpts (see base.py)."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx2

from sanad.llm.base import Delta, Done, HostedProvider, LlmUnavailableError, Stopwatch, TextDelta
from sanad.llm.prompts import Prompt


class OpenAICompatProvider(HostedProvider):
    name = "openai_compat"

    def __init__(
        self,
        model: str,
        *,
        base_url: str,
        api_key: str | None,
        max_output_tokens: int,
        timeout_seconds: float,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(model)
        self._max_output_tokens = max_output_tokens
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx2.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
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
            "temperature": 0,
            "max_tokens": self._max_output_tokens,
        }

    async def _stream(self, prompt: Prompt) -> AsyncIterator[Delta]:
        watch = Stopwatch()
        usage: dict[str, Any] = {}
        try:
            async with self._client.stream(
                "POST", "/chat/completions", json=self._body(prompt)
            ) as resp:
                if resp.status_code != 200:
                    await resp.aread()
                    raise LlmUnavailableError(f"openai_compat answered {resp.status_code}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    usage = chunk.get("usage") or usage
                    for choice in chunk.get("choices") or []:
                        text = (choice.get("delta") or {}).get("content") or ""
                        if text:
                            watch.text_arrived()
                            yield TextDelta(text)
        except (httpx2.HTTPError, ValueError) as exc:
            raise LlmUnavailableError(f"openai_compat: {type(exc).__name__}") from exc
        prompt_ms, output_ms = watch.split_ms()
        yield Done(
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            prompt_ms=prompt_ms,
            output_ms=output_ms,
        )
