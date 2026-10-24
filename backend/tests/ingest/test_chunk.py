"""DECISIONS D1 chunking, with a whitespace "tokenizer" so sizes are easy to reason about.

The real bge-m3 tokenizer is exercised against the running ml service in test_ml_live.py.
"""

from collections.abc import Sequence

import pytest

from sanad.ingest.chunk import Chunk, ChunkParams, chunk_document, chunk_page


def words(texts: Sequence[str]) -> list[int]:
    return [len(t.split()) for t in texts]


def sentence(n: int, word: str = "كلمة") -> str:
    """A sentence of exactly n words ending in a full stop."""
    return " ".join([word] * n) + "."


def paragraph(*sizes: int, word: str = "كلمة") -> str:
    return " ".join(sentence(n, word) for n in sizes)


PARAMS = ChunkParams(target_tokens=100, max_tokens=150, overlap_tokens=15, min_tail_tokens=25)


def chunks_of(pages: list[str], params: ChunkParams = PARAMS) -> list[Chunk]:
    return chunk_document(pages, words, params)


def test_chunks_are_exact_slices_of_their_page() -> None:
    pages = ["\n\n".join(paragraph(20, 20, 20) for _ in range(4)), paragraph(30, 30)]
    for chunk in chunks_of(pages):
        page = pages[chunk.page_number - 1]
        assert chunk.text == page[chunk.char_start : chunk.char_end]
        assert chunk.text == chunk.text.strip()


def test_chunks_never_cross_a_page_boundary_and_are_numbered_in_order() -> None:
    pages = [paragraph(40, 40, 40), "", paragraph(10), "  \n\n ", paragraph(60, 60)]
    result = chunks_of(pages)
    assert [c.chunk_index for c in result] == list(range(len(result)))
    assert {c.page_number for c in result} == {1, 3, 5}
    assert [c.page_number for c in result] == sorted(c.page_number for c in result)


def test_sizes_stay_near_the_target_and_under_the_hard_maximum() -> None:
    page = "\n\n".join(paragraph(12, 9, 15, 7) for _ in range(12))
    result = chunks_of([page])
    assert len(result) > 3
    for chunk in result:
        assert chunk.token_count <= PARAMS.max_tokens
        assert chunk.token_count == len(chunk.text.split())
    # Every chunk but the last carries at least half the target of new text.
    assert all(c.token_count >= PARAMS.target_tokens // 2 for c in result[:-1])


def test_consecutive_chunks_on_a_page_overlap_by_whole_sentences() -> None:
    page = paragraph(*[10] * 30)
    result = chunks_of([page])
    assert len(result) >= 3
    for prev, nxt in zip(result, result[1:], strict=False):
        assert nxt.char_start < prev.char_end  # they overlap
        shared = page[nxt.char_start : prev.char_end]
        assert shared.endswith(".")  # whole sentences
        assert 10 <= len(shared.split()) <= 2 * PARAMS.overlap_tokens


def test_overlap_rounds_to_the_nearest_whole_sentence() -> None:
    # Last sentence before the cut has 20 words: nearer 15 than 0 is 20, so it is carried.
    page = paragraph(40, 40, 20, 40, 40)
    first, second = chunks_of([page])[:2]
    assert page[second.char_start : first.char_end] == sentence(20)
    # A 40-word last sentence is too far from 15 (and over 2 x 15): no overlap at all.
    page = paragraph(30, 30, 40, 40, 40)
    first, second = chunks_of([page])[:2]
    assert second.char_start >= first.char_end


def test_no_overlap_when_disabled() -> None:
    params = ChunkParams(target_tokens=100, max_tokens=150, overlap_tokens=0, min_tail_tokens=0)
    result = chunks_of([paragraph(*[10] * 30)], params)
    for prev, nxt in zip(result, result[1:], strict=False):
        assert nxt.char_start >= prev.char_end


def test_chunks_end_at_paragraph_boundaries_when_half_full() -> None:
    params = ChunkParams(target_tokens=100, max_tokens=150, overlap_tokens=0, min_tail_tokens=25)
    paragraphs = [paragraph(30, 30), paragraph(25, 25), paragraph(40, 40), paragraph(20, 30)]
    # 60 words, and 50 more would pass 100: the chunk closes at the paragraph boundary
    # instead of taking half of the next paragraph. Likewise for every later chunk.
    result = chunks_of(["\n\n".join(paragraphs)], params)
    assert [c.text for c in result] == paragraphs


def test_a_small_chunk_fills_up_from_the_next_paragraph() -> None:
    params = ChunkParams(target_tokens=100, max_tokens=150, overlap_tokens=0, min_tail_tokens=0)
    # 30 words is under half the target, so the chunk takes sentences of the next paragraph.
    page = "\n\n".join([paragraph(30), paragraph(40, 40, 40)])
    result = chunks_of([page], params)
    assert result[0].token_count == 70
    assert "\n\n" in result[0].text


def test_short_page_tail_merges_into_the_previous_chunk() -> None:
    # 95 words fill the first chunk; the 20-word tail is under 25 and merges.
    page = paragraph(45, 50, 20)
    result = chunks_of([page])
    assert len(result) == 1
    assert result[0].char_end == len(page)
    assert result[0].token_count == 115


def test_tail_at_or_above_the_minimum_stays_separate() -> None:
    page = paragraph(45, 50, 30)
    result = chunks_of([page])
    assert len(result) == 2
    assert result[-1].char_end == len(page)


def test_tail_does_not_merge_past_the_hard_maximum() -> None:
    params = ChunkParams(target_tokens=100, max_tokens=110, overlap_tokens=0, min_tail_tokens=50)
    result = chunks_of([paragraph(50, 50, 20)], params)
    assert len(result) == 2


def test_a_short_page_is_one_chunk() -> None:
    result = chunks_of([paragraph(5)])
    assert len(result) == 1
    assert result[0].token_count == 5


def test_long_lines_without_sentence_ends_split_at_line_breaks() -> None:
    # A table: 40 rows of 8 cells, no full stops, one "sentence" for the splitter.
    rows = ["خلية " * 7 + "خلية" for _ in range(40)]
    page = "\n".join(rows)
    result = chunks_of([page])
    assert len(result) >= 3
    for chunk in result:
        assert chunk.token_count <= PARAMS.max_tokens
        assert chunk.text.startswith("خلية") and chunk.text.endswith("خلية")
        assert chunk.text.count("\n") + 1 == chunk.token_count // 8  # whole rows only


def test_a_huge_line_splits_at_spaces() -> None:
    page = " ".join(f"w{i}" for i in range(450))
    result = chunks_of([page])
    assert len(result) >= 4
    assert all(c.token_count <= PARAMS.target_tokens + 2 * PARAMS.overlap_tokens for c in result)
    covered = " ".join(page[c.char_start : c.char_end] for c in result)
    assert covered.split()[-1] == "w449"


def test_a_single_word_over_the_target_is_kept_whole() -> None:
    def chars(texts: Sequence[str]) -> list[int]:
        return [len(t) for t in texts]

    params = ChunkParams(target_tokens=10, max_tokens=20, overlap_tokens=0, min_tail_tokens=0)
    (chunk,) = chunk_document(["x" * 30], chars, params)
    assert chunk.text == "x" * 30


def test_recount_over_the_maximum_splits_the_chunk() -> None:
    # A tokenizer whose counts are not additive: each sentence boundary inside a text costs
    # 15 extra tokens, so 11 sentences of 9 "tokens" pack to 99 but recount to 249.
    def sticky(texts: Sequence[str]) -> list[int]:
        return [len(t.split()) + 15 * t.count(". ") for t in texts]

    params = ChunkParams(target_tokens=100, max_tokens=110, overlap_tokens=0, min_tail_tokens=0)
    page = paragraph(*[9] * 11)
    spans = chunk_page(page, sticky, params)
    assert len(spans) >= 3
    assert all(tokens <= params.max_tokens for _, _, tokens in spans)
    assert spans[0][0] == 0 and spans[-1][1] == len(page)


def test_empty_document() -> None:
    assert chunks_of([]) == []
    assert chunks_of(["", "\n\n"]) == []


def test_default_parameters_follow_d1() -> None:
    params = ChunkParams()
    assert (params.target_tokens, params.max_tokens) == (350, 512)
    assert (params.overlap_tokens, params.min_tail_tokens) == (50, 80)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_tokens": 0},
        {"target_tokens": 600},
        {"target_tokens": 450, "overlap_tokens": 50},
        {"overlap_tokens": -1},
        {"min_tail_tokens": -1},
    ],
)
def test_invalid_parameters_are_rejected(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="tokens"):
        ChunkParams(**kwargs)
