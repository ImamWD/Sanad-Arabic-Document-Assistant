"""Provider adapters against mocked HTTP: request shape, stream parsing, errors, and the
hosted-provider guard (no request at all for a non-seed excerpt)."""

import json
from collections.abc import Callable

import anthropic
import httpx2
import pytest
from pydantic import SecretStr

from sanad.llm.anthropic import FALLBACK_BETA, MAX_TOKENS, AnthropicProvider
from sanad.llm.base import (
    Delta,
    Done,
    HostedNonSeedDataError,
    LlmProvider,
    LlmUnavailableError,
    TextDelta,
)
from sanad.llm.ollama import OllamaProvider
from sanad.llm.openai_compat import OpenAICompatProvider
from sanad.llm.prompts import Excerpt, Prompt, build_prompt
from sanad.llm.providers import ProviderConfigError, build_provider
from sanad.llm.settings import DEFAULT_ANTHROPIC_MODEL, DEFAULT_OLLAMA_MODEL, LlmSettings

pytestmark = pytest.mark.anyio

Handler = Callable[[httpx2.Request], httpx2.Response]


def seed_prompt(seed: bool = True) -> Prompt:
    excerpt = Excerpt("Annual Report 2023", 3, "About 2,400 girls followed the radio.", "en", seed)
    return build_prompt("How many girls followed the radio lessons?", [excerpt])


async def collect(provider: LlmProvider, prompt: Prompt) -> list[Delta]:
    try:
        return [d async for d in provider.stream(prompt)]
    finally:
        await provider.aclose()


def recorder(handler: Handler) -> tuple[httpx2.MockTransport, list[httpx2.Request]]:
    seen: list[httpx2.Request] = []

    def wrapped(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return handler(request)

    return httpx2.MockTransport(wrapped), seen


def ollama(transport: httpx2.MockTransport) -> OllamaProvider:
    return OllamaProvider(
        "sanad-gemma4-e4b-text",
        base_url="http://ollama:11434",
        num_ctx=8192,
        max_output_tokens=512,
        keep_alive="30m",
        timeout_seconds=5,
        transport=transport,
    )


def ndjson(*chunks: dict[str, object]) -> bytes:
    return b"".join(json.dumps(c).encode() + b"\n" for c in chunks)


async def test_ollama_request_and_stream() -> None:
    body = ndjson(
        {"message": {"role": "assistant", "content": "About 2,400 "}, "done": False},
        {"message": {"role": "assistant", "content": "girls [1]."}, "done": False},
        {
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "prompt_eval_count": 410,
            "eval_count": 9,
        },
    )
    transport, seen = recorder(lambda _: httpx2.Response(200, content=body))
    deltas = await collect(ollama(transport), seed_prompt())

    assert deltas[:2] == [TextDelta("About 2,400 "), TextDelta("girls [1].")]
    done = deltas[2]
    assert isinstance(done, Done)
    assert (done.prompt_tokens, done.completion_tokens, done.refused) == (410, 9, False)
    (request,) = seen
    assert str(request.url) == "http://ollama:11434/api/chat"
    sent = json.loads(request.content)
    assert sent["model"] == "sanad-gemma4-e4b-text"
    assert sent["stream"] is True and sent["think"] is False
    assert sent["options"] == {"temperature": 0, "num_ctx": 8192, "num_predict": 512}
    assert [m["role"] for m in sent["messages"]] == ["system", "user"]


async def test_ollama_missing_model_is_unavailable() -> None:
    transport, _ = recorder(lambda _: httpx2.Response(404, json={"error": "model not found"}))
    with pytest.raises(LlmUnavailableError):
        await collect(ollama(transport), seed_prompt())


async def test_ollama_error_mid_stream_is_unavailable() -> None:
    body = ndjson({"message": {"content": "Abo"}, "done": False}, {"error": "out of memory"})
    transport, _ = recorder(lambda _: httpx2.Response(200, content=body))
    with pytest.raises(LlmUnavailableError):
        await collect(ollama(transport), seed_prompt())


async def test_ollama_unreachable_is_unavailable() -> None:
    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused", request=request)

    transport, _ = recorder(refuse)
    with pytest.raises(LlmUnavailableError):
        await collect(ollama(transport), seed_prompt())


async def test_ollama_stream_without_done_is_unavailable() -> None:
    transport, _ = recorder(
        lambda _: httpx2.Response(200, content=ndjson({"message": {"content": "x"}}))
    )
    with pytest.raises(LlmUnavailableError):
        await collect(ollama(transport), seed_prompt())


def openai_compat(
    transport: httpx2.MockTransport, key: str | None = "test-key"
) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        "gemma-reference",
        base_url="https://llm.example.org/v1/",
        api_key=key,
        max_output_tokens=512,
        timeout_seconds=5,
        transport=transport,
    )


def sse_lines(*payloads: object) -> bytes:
    return b"".join(
        f"data: {p if isinstance(p, str) else json.dumps(p)}\n\n".encode() for p in payloads
    )


async def test_openai_compat_request_and_stream() -> None:
    body = sse_lines(
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"content": "About 2,400 girls "}}]},
        {"choices": [{"delta": {"content": "[1]."}}]},
        {"choices": [], "usage": {"prompt_tokens": 400, "completion_tokens": 8}},
        "[DONE]",
    )
    transport, seen = recorder(lambda _: httpx2.Response(200, content=body))
    deltas = await collect(openai_compat(transport), seed_prompt())

    assert deltas[:2] == [TextDelta("About 2,400 girls "), TextDelta("[1].")]
    done = deltas[-1]
    assert isinstance(done, Done) and (done.prompt_tokens, done.completion_tokens) == (400, 8)
    (request,) = seen
    assert str(request.url) == "https://llm.example.org/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer test-key"
    sent = json.loads(request.content)
    assert (sent["model"], sent["temperature"], sent["stream"]) == ("gemma-reference", 0, True)


async def test_openai_compat_error_status_is_unavailable() -> None:
    transport, _ = recorder(lambda _: httpx2.Response(429, json={"error": "rate limited"}))
    with pytest.raises(LlmUnavailableError):
        await collect(openai_compat(transport, key=None), seed_prompt())


async def test_openai_compat_refuses_non_seed_excerpts_without_a_request() -> None:
    transport, seen = recorder(lambda _: httpx2.Response(200, content=sse_lines("[DONE]")))
    with pytest.raises(HostedNonSeedDataError):
        await collect(openai_compat(transport), seed_prompt(seed=False))
    assert seen == []


def anthropic_sse(stop_reason: str = "end_turn", text: str = "About 2,400 girls [1].") -> bytes:
    events: list[tuple[str, dict[str, object]]] = [
        (
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "model": DEFAULT_ANTHROPIC_MODEL,
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 420, "output_tokens": 1},
                },
            },
        ),
        (
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
        ),
        (
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": text},
            },
        ),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        (
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"output_tokens": 12},
            },
        ),
        ("message_stop", {"type": "message_stop"}),
    ]
    return b"".join(
        f"event: {name}\ndata: {json.dumps(data)}\n\n".encode() for name, data in events
    )


def claude(handler: Handler) -> tuple[AnthropicProvider, list[httpx2.Request]]:
    transport, seen = recorder(handler)
    client = anthropic.AsyncAnthropic(
        api_key="test-key",
        base_url="https://anthropic.example.org",
        http_client=httpx2.AsyncClient(transport=transport),
        max_retries=0,
    )
    return AnthropicProvider(DEFAULT_ANTHROPIC_MODEL, client=client), seen


async def test_anthropic_request_and_stream() -> None:
    provider, seen = claude(
        lambda _: httpx2.Response(
            200, content=anthropic_sse(), headers={"content-type": "text/event-stream"}
        )
    )
    deltas = await collect(provider, seed_prompt())

    assert deltas[0] == TextDelta("About 2,400 girls [1].")
    done = deltas[-1]
    assert isinstance(done, Done)
    assert (done.prompt_tokens, done.completion_tokens, done.refused) == (420, 12, False)
    (request,) = seen
    sent = json.loads(request.content)
    assert sent["model"] == DEFAULT_ANTHROPIC_MODEL
    assert sent["max_tokens"] == MAX_TOKENS
    assert sent["fallbacks"] == "default"
    assert sent["output_config"] == {"effort": "medium"}
    assert FALLBACK_BETA in request.headers["anthropic-beta"]
    # Sampling parameters are rejected by the API: never sent.
    assert not {"temperature", "top_p", "top_k"} & sent.keys()


async def test_anthropic_refusal_is_reported() -> None:
    provider, _ = claude(
        lambda _: httpx2.Response(
            200,
            content=anthropic_sse(stop_reason="refusal", text=""),
            headers={"content-type": "text/event-stream"},
        )
    )
    done = (await collect(provider, seed_prompt()))[-1]
    assert isinstance(done, Done) and done.refused


async def test_anthropic_error_is_unavailable() -> None:
    provider, _ = claude(
        lambda _: httpx2.Response(
            529, json={"type": "error", "error": {"type": "overloaded_error", "message": "busy"}}
        )
    )
    with pytest.raises(LlmUnavailableError):
        await collect(provider, seed_prompt())


async def test_anthropic_refuses_non_seed_excerpts_without_a_request() -> None:
    provider, seen = claude(lambda _: httpx2.Response(500))
    with pytest.raises(HostedNonSeedDataError):
        await collect(provider, seed_prompt(seed=False))
    assert seen == []


async def test_build_provider_defaults_to_ollama() -> None:
    provider = build_provider(LlmSettings())
    try:
        assert isinstance(provider, OllamaProvider)
        assert provider.model == DEFAULT_OLLAMA_MODEL
        assert not provider.hosted
    finally:
        await provider.aclose()


async def test_build_provider_hosted_variants() -> None:
    claude_provider = build_provider(
        LlmSettings(llm_provider="anthropic", anthropic_api_key=SecretStr("test-key"))
    )
    compat = build_provider(
        LlmSettings(
            llm_provider="openai_compat",
            llm_model="gemma-reference",
            openai_compat_base_url="https://llm.example.org/v1",
        )
    )
    try:
        assert isinstance(claude_provider, AnthropicProvider) and claude_provider.hosted
        assert claude_provider.model == DEFAULT_ANTHROPIC_MODEL
        assert isinstance(compat, OpenAICompatProvider) and compat.hosted
    finally:
        await claude_provider.aclose()
        await compat.aclose()


def test_openai_compat_needs_its_settings() -> None:
    with pytest.raises(ProviderConfigError):
        build_provider(LlmSettings(llm_provider="openai_compat"))
