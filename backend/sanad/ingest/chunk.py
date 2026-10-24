"""Page-bounded, paragraph-aligned chunking (DECISIONS D1).

- Sizes are in tokens of the embedding model's own tokenizer (bge-m3), never characters:
  Arabic attaches clitics, so character and word counts both mislead. The counter is
  injected, so the worker passes the ml service's /tokenize and tests pass a fake.
- A chunk never crosses a page boundary, so every citation names exactly one page.
- Chunks are built from whole sentences (`sanad.text.arabic.sentence_spans`), and close at a
  paragraph boundary whenever the chunk is at least half full.
- About 350 tokens per chunk, never more than 512. Consecutive chunks on a page overlap by
  about 50 tokens, rounded to whole sentences.
- A page tail under 80 tokens merges into the previous chunk on the same page.

Every chunk is an exact slice of the cleaned page text: `text == page[char_start:char_end]`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sanad.text.arabic import sentence_spans

TokenCounter = Callable[[Sequence[str]], list[int]]
"""Token counts of each text, without special tokens."""

_PARAGRAPH_BREAK = re.compile(r"\n[^\S\n]*\n\s*")
_LINE = re.compile(r"[^\n]+")
_WORD = re.compile(r"\S+")


@dataclass(frozen=True)
class ChunkParams:
    target_tokens: int = 350
    max_tokens: int = 512
    overlap_tokens: int = 50
    min_tail_tokens: int = 80

    def __post_init__(self) -> None:
        if not 0 < self.target_tokens <= self.max_tokens:
            raise ValueError("need 0 < target_tokens <= max_tokens")
        # Worst case: a full overlap (2 x overlap) plus one unit of target size must fit.
        if self.target_tokens + 2 * self.overlap_tokens > self.max_tokens:
            raise ValueError("target_tokens + 2 * overlap_tokens must not exceed max_tokens")
        if self.overlap_tokens < 0 or self.min_tail_tokens < 0:
            raise ValueError("overlap_tokens and min_tail_tokens must be >= 0")


@dataclass(frozen=True)
class Chunk:
    page_number: int  # 1-based, the page in the viewer PDF
    chunk_index: int  # 0-based, unique within the document
    char_start: int  # offsets into the cleaned page text (document_pages.text)
    char_end: int
    text: str
    token_count: int


@dataclass(frozen=True)
class _Unit:
    """A sentence, or a piece of an over-long one, inside one paragraph."""

    start: int
    end: int
    tokens: int


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    start = 0
    for match in _PARAGRAPH_BREAK.finditer(text):
        spans.append((start, match.start()))
        start = match.end()
    spans.append((start, len(text)))
    return [(s, e) for s, e in spans if text[s:e].strip()]


def _sub_spans(text: str, start: int, end: int, pattern: re.Pattern[str]) -> list[tuple[int, int]]:
    return [(start + m.start(), start + m.end()) for m in pattern.finditer(text[start:end])]


def _pack(spans: list[tuple[int, int]], tokens: list[int], limit: int) -> list[_Unit]:
    """Greedily group consecutive spans into units of at most `limit` tokens (sum of parts)."""
    units: list[_Unit] = []
    start = end = total = -1
    for (s, e), n in zip(spans, tokens, strict=True):
        if total >= 0 and total + n <= limit:
            end, total = e, total + n
            continue
        if total >= 0:
            units.append(_Unit(start, end, total))
        start, end, total = s, e, n
    if total >= 0:
        units.append(_Unit(start, end, total))
    return units


def _split_long(
    text: str, unit: _Unit, count: TokenCounter, limit: int, by: list[re.Pattern[str]]
) -> list[_Unit]:
    """Split a unit over `limit` tokens at line breaks, then at spaces (tables, long lists)."""
    if unit.tokens <= limit or not by:
        return [unit]
    spans = _sub_spans(text, unit.start, unit.end, by[0])
    if len(spans) <= 1:
        return _split_long(text, unit, count, limit, by[1:])
    tokens = count([text[s:e] for s, e in spans])
    pieces = _pack(spans, tokens, limit)
    return [p for piece in pieces for p in _split_long(text, piece, count, limit, by[1:])]


def _units(text: str, count: TokenCounter, params: ChunkParams) -> list[list[_Unit]]:
    """Paragraphs of the page, each a list of sentence units no longer than the target."""
    paragraphs = []
    for p_start, p_end in _paragraph_spans(text):
        spans = [(p_start + s, p_start + e) for s, e in sentence_spans(text[p_start:p_end])]
        paragraphs.append(spans)
    flat = [span for spans in paragraphs for span in spans]
    if not flat:
        return []
    tokens = iter(count([text[s:e] for s, e in flat]))
    result = []
    for spans in paragraphs:
        units: list[_Unit] = []
        for s, e in spans:
            unit = _Unit(s, e, next(tokens))
            units.extend(_split_long(text, unit, count, params.target_tokens, [_LINE, _WORD]))
        result.append(units)
    return result


def _overlap(units: list[_Unit], target: int) -> list[_Unit]:
    """Trailing units of a closed chunk whose total is nearest `target` (at most 2 x target),
    never the whole chunk. Rounding to whole sentences means a 70-token last sentence is kept
    for a 50-token target, and a 120-token one is not."""
    best: list[_Unit] = []
    best_gap = target
    total = 0
    for k in range(1, len(units)):
        total += units[-k].tokens
        if total > 2 * target:
            break
        if abs(total - target) < best_gap:
            best, best_gap = units[-k:], abs(total - target)
    return best


class _PageBuilder:
    def __init__(self, params: ChunkParams) -> None:
        self.params = params
        self.closed: list[list[_Unit]] = []
        self.current: list[_Unit] = []
        self.carried = 0  # how many leading units of `current` are overlap from the last chunk

    @property
    def tokens(self) -> int:
        return sum(u.tokens for u in self.current)

    @property
    def fresh_tokens(self) -> int:
        return sum(u.tokens for u in self.current[self.carried :])

    def close(self) -> None:
        self.closed.append(self.current)
        self.current = _overlap(self.current, self.params.overlap_tokens)
        self.carried = len(self.current)

    def add_paragraph(self, units: list[_Unit]) -> None:
        target = self.params.target_tokens
        size = sum(u.tokens for u in units)
        if self.tokens + size <= target:
            self.current.extend(units)
            return
        if self.fresh_tokens >= target // 2:
            # Half full or more: end the chunk at this paragraph boundary.
            self.close()
            if self.tokens + size <= target:
                self.current.extend(units)
                return
        for unit in units:
            if self.fresh_tokens > 0 and self.tokens + unit.tokens > target:
                self.close()
            self.current.append(unit)

    def finish(self) -> list[list[_Unit]]:
        if self.fresh_tokens > 0:
            tail = self.current[self.carried :]
            tail_tokens = sum(u.tokens for u in tail)
            previous = self.closed[-1] if self.closed else None
            if (
                previous is not None
                and tail_tokens < self.params.min_tail_tokens
                and sum(u.tokens for u in previous) + tail_tokens <= self.params.max_tokens
            ):
                previous.extend(tail)
            else:
                self.closed.append(self.current)
        return self.closed


def _halve(units: list[_Unit]) -> tuple[list[_Unit], list[_Unit]]:
    total = sum(u.tokens for u in units)
    running = 0
    for i, unit in enumerate(units[:-1]):
        running += unit.tokens
        if running >= total / 2:
            return units[: i + 1], units[i + 1 :]
    return units[:-1], units[-1:]


def chunk_page(
    text: str, count: TokenCounter, params: ChunkParams
) -> list[tuple[int, int, int]]:
    """(char_start, char_end, token_count) of each chunk of one cleaned page, in order."""
    builder = _PageBuilder(params)
    for units in _units(text, count, params):
        builder.add_paragraph(units)
    groups = builder.finish()
    # Token counts are only nearly additive across sentence boundaries, so recount the real
    # chunk texts and split any chunk that the recount puts over the hard maximum.
    while True:
        counts = count([text[g[0].start : g[-1].end] for g in groups])
        over = [i for i, n in enumerate(counts) if n > params.max_tokens and len(groups[i]) > 1]
        if not over:
            break
        i = over[0]
        groups[i : i + 1] = list(_halve(groups[i]))
    return [(g[0].start, g[-1].end, n) for g, n in zip(groups, counts, strict=True)]


def chunk_document(
    pages: Sequence[str], count: TokenCounter, params: ChunkParams | None = None
) -> list[Chunk]:
    """Chunk every page of a document. `pages[i]` is page i + 1 of the viewer PDF."""
    params = params or ChunkParams()
    chunks: list[Chunk] = []
    for page_index, text in enumerate(pages):
        for start, end, tokens in chunk_page(text, count, params):
            chunks.append(
                Chunk(
                    page_number=page_index + 1,
                    chunk_index=len(chunks),
                    char_start=start,
                    char_end=end,
                    text=text[start:end],
                    token_count=tokens,
                )
            )
    return chunks
