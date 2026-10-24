"""Fakes for the ask pipeline: a scripted LLM, canned retrieval and an in-memory query store.

The excerpt texts are invented in the style of the seed corpus (synthetic, like it).
"""

import asyncio
import re
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import ClassVar

from sanad.core import passwords
from sanad.core.models import Language, Role, User
from sanad.llm.base import Delta, Done, HostedProvider, LlmProvider, LlmUnavailableError, TextDelta
from sanad.llm.eta import PerfSample
from sanad.llm.prompts import Prompt
from sanad.llm.queue import GenerationQueue
from sanad.llm.settings import LlmSettings
from sanad.retrieval.pipeline import AskInput, AskPipeline, Event
from sanad.retrieval.settings import RetrievalSettings
from sanad.retrieval.types import Candidate, Filters, QueryRecord, Retrieved


def make_user(
    role: Role = Role.VIEWER, *, guest: bool = False, lang: Language = Language.EN
) -> User:
    return User(
        id=uuid.uuid4(),
        name="Test User",
        email=f"{uuid.uuid4().hex[:8]}@sanad.example",
        password_hash=passwords.UNUSABLE_PASSWORD_HASH,
        role=role,
        preferred_language=lang,
        is_active=True,
        is_guest=guest,
    )


def make_candidate(
    text: str = "بلغ عدد المستفيدين الملتحقين بسوق العمل 538 شاباً وشابة في عام 2021.",
    *,
    score: float = 0.9,
    title: str = "التقرير السنوي 2021",
    page: int = 6,
    is_seed: bool = True,
    file_type: str = "pdf",
    language: str | None = "ar",
    document_id: uuid.UUID | None = None,
) -> Candidate:
    return Candidate(
        chunk_id=uuid.uuid4(),
        document_id=document_id or uuid.uuid4(),
        title=title,
        page_number=page,
        text=text,
        char_start=0,
        char_end=len(text),
        file_type=file_type,
        is_converted=file_type != "pdf",
        is_seed=is_seed,
        language=language,
        score=score,
    )


class FakeRetriever:
    def __init__(self, candidates: Sequence[Candidate], error: Exception | None = None) -> None:
        self.candidates = sorted(candidates, key=lambda c: -c.score)
        self.error = error
        self.calls: list[tuple[User, str, Filters]] = []
        self.timings_ms: dict[str, int] = {}

    async def retrieve(self, user: User, question: str, filters: Filters) -> Retrieved:
        self.calls.append((user, question, filters))
        if self.error is not None:
            raise self.error
        return Retrieved(list(self.candidates), dict(self.timings_ms))


@dataclass
class FakeStore:
    saved: list[QueryRecord] = field(default_factory=list)
    samples: list[PerfSample] = field(default_factory=list)

    async def recent_perf(self, llm_model: str, limit: int) -> list[PerfSample]:
        return self.samples[:limit]

    async def save(self, record: QueryRecord) -> uuid.UUID:
        self.saved.append(record)
        return uuid.uuid4()


class FakeLlm(LlmProvider):
    """Streams the scripted pieces, then `Done`. Records every prompt it was given."""

    name = "fake"

    def __init__(
        self,
        pieces: Sequence[str] = (),
        *,
        refused: bool = False,
        fail: bool = False,
        model: str = "fake-model",
    ) -> None:
        super().__init__(model)
        self.pieces = list(pieces)
        self.refused = refused
        self.fail = fail
        self.prompts: list[Prompt] = []

    async def stream(self, prompt: Prompt) -> AsyncIterator[Delta]:
        self.prompts.append(prompt)
        if self.fail:
            raise LlmUnavailableError("fake")
        for piece in self.pieces:
            yield TextDelta(piece)
        yield Done(
            prompt_tokens=len(prompt.user) // 3,
            completion_tokens=len(self.pieces),
            prompt_ms=1200,
            output_ms=300,
            refused=self.refused,
        )


_EXCERPT_HEADER = re.compile(r"^\[(\d+)\] .*$", re.MULTILINE)


def excerpt_bodies(prompt: Prompt) -> dict[int, str]:
    """The excerpts of a built prompt, by number."""
    block = prompt.user.split("\n\nQuestion:")[0]
    heads = list(_EXCERPT_HEADER.finditer(block))
    return {
        int(h.group(1)): block[h.end() : heads[i + 1].start() if i + 1 < len(heads) else None]
        for i, h in enumerate(heads)
    }


class GroundedLlm(LlmProvider):
    """Behaves like a model that keeps the contract: it answers a question it recognises (by a
    keyword) only if an excerpt holds that question's fact, citing that excerpt; otherwise
    NO_ANSWER. `delay` holds the first token back (a slow CPU prompt)."""

    name = "grounded"
    # Question keyword -> the fact that answers it (from the seed corpus).
    FACTS: ClassVar[dict[str, str]] = {
        "رواتب": "84,000",
        "volunteers": "455",
        "سوق العمل": "538",
        "الراضية": "91%",
    }

    def __init__(self, delay: float = 0.0) -> None:
        super().__init__("grounded-model")
        self.delay = delay
        self.prompts: list[Prompt] = []

    async def stream(self, prompt: Prompt) -> AsyncIterator[Delta]:
        self.prompts.append(prompt)
        if self.delay:
            await asyncio.sleep(self.delay)
        question = prompt.user.split("\n\nQuestion:")[1]
        wanted = [fact for key, fact in self.FACTS.items() if key in question]
        answer = "NO_ANSWER"
        for n, body in excerpt_bodies(prompt).items():
            fact = next((f for f in wanted if f in body), None)
            if fact is not None:
                answer = f"The excerpts give the figure {fact} [{n}]."
                break
        for word in answer.split(" "):
            yield TextDelta(word + " ")
        yield Done(None, None, prompt_ms=900, output_ms=100)


class FakeHostedLlm(HostedProvider):
    """A hosted provider whose `_stream` must never run for non-seed excerpts."""

    name = "fake_hosted"

    def __init__(self, pieces: Sequence[str] = ()) -> None:
        super().__init__("fake-hosted-model")
        self.pieces = list(pieces)
        self.sent: list[Prompt] = []

    async def _stream(self, prompt: Prompt) -> AsyncIterator[Delta]:
        self.sent.append(prompt)
        for piece in self.pieces:
            yield TextDelta(piece)
        yield Done(None, None, prompt_ms=10, output_ms=10)


RETRIEVAL = RetrievalSettings(t_refuse=0.2, t_confident=0.6, retrieval_top_k=3)
LLM = LlmSettings(eta_default_seconds=45)


def pipeline(
    retriever: FakeRetriever,
    llm: LlmProvider,
    store: FakeStore | None = None,
    queue: GenerationQueue | None = None,
) -> tuple[AskPipeline, FakeStore]:
    store = store or FakeStore()
    return (
        AskPipeline(
            retriever=retriever,
            store=store,
            provider=llm,
            queue=queue or GenerationQueue(1),
            retrieval=RETRIEVAL,
            llm=LLM,
        ),
        store,
    )


async def run(p: AskPipeline, question: str = "كم شاباً حصل على عمل في 2021؟") -> list[Event]:
    ask = AskInput(user=make_user(), session_id="s1", question=question)
    return [event async for event in p.run(ask)]


def names(events: Sequence[Event]) -> list[str]:
    """Event names, with the stage spelled out: ["stage:searching", "eta", "token", ...]."""
    return [f"stage:{e.data['stage']}" if e.name == "stage" else e.name for e in events]
