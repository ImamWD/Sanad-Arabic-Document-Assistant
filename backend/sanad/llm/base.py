"""What the ask pipeline needs from an LLM provider, and the hosted-provider guard.

A provider streams `TextDelta`s and ends with exactly one `Done`. Failures to reach the model
raise `LlmUnavailableError`; the pipeline turns that into the LLM_UNAVAILABLE error code.

Hosted providers (`openai_compat`, `anthropic`) are for benchmarks on the synthetic seed corpus
only (DECISIONS D3). `HostedProvider.stream` checks the prompt before anything is sent: if any
excerpt comes from a non-seed document it raises `HostedNonSeedDataError` and makes no call,
even when the api-llm override was applied by mistake (SYSTEM_DESIGN §9).
"""

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sanad.llm.prompts import Prompt


class LlmUnavailableError(Exception):
    """The model couldn't be reached, or it answered with an error."""


class HostedNonSeedDataError(Exception):
    """A hosted provider was asked to send an excerpt from a non-seed document."""


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class Done:
    """End of generation. Token counts are the provider's own, when it reports them. The
    timings are measured here: request start to first text, and first text to the end."""

    prompt_tokens: int | None
    completion_tokens: int | None
    prompt_ms: int
    output_ms: int
    # The provider declined to answer (a safety refusal). The pipeline treats it as the
    # sentinel: the model found nothing it could answer with.
    refused: bool = False


Delta = TextDelta | Done


class Stopwatch:
    """Splits a generation into prompt time (until the first text) and output time."""

    def __init__(self) -> None:
        self._start = time.monotonic()
        self._first: float | None = None

    def text_arrived(self) -> None:
        if self._first is None:
            self._first = time.monotonic()

    def split_ms(self) -> tuple[int, int]:
        end = time.monotonic()
        first = self._first if self._first is not None else end
        return round((first - self._start) * 1000), round((end - first) * 1000)


class LlmProvider(ABC):
    name: str
    hosted: bool = False

    def __init__(self, model: str) -> None:
        self.model = model

    @abstractmethod
    def stream(self, prompt: Prompt) -> AsyncIterator[Delta]:
        """Generate an answer to `prompt`, streaming text as it arrives."""

    async def aclose(self) -> None:  # noqa: B027 - optional hook, most providers hold nothing
        """Release connections held by the provider."""


class HostedProvider(LlmProvider, ABC):
    hosted = True

    def stream(self, prompt: Prompt) -> AsyncIterator[Delta]:
        if not prompt.all_seed:
            raise HostedNonSeedDataError(self.name)
        return self._stream(prompt)

    @abstractmethod
    def _stream(self, prompt: Prompt) -> AsyncIterator[Delta]:
        """Send the (checked) prompt to the hosted model."""
