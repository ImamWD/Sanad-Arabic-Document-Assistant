"""Reciprocal-rank fusion of the dense and lexical rankings."""

from collections.abc import Hashable, Sequence


def rrf[K: Hashable](rankings: Sequence[Sequence[K]], *, k: int, limit: int) -> list[K]:
    """Fuse best-first rankings: each item scores the sum of 1 / (k + rank) over the rankings
    it appears in (rank from 1). Ties keep first-seen order, so the result is deterministic."""
    scores: dict[K, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    order = {item: i for i, item in enumerate(scores)}
    return sorted(scores, key=lambda item: (-scores[item], order[item]))[:limit]
