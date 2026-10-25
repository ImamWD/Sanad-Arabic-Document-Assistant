"""Scoring rules (SYSTEM_DESIGN §11) and failure categories. Pure functions, no I/O.

An answerable item is correct only if:
- its outcome is `answered` or `low_confidence`, and
- every `must_include` fact is in the answer, and
- at least one citation is an expected `(file, page)`.

An unanswerable item is correct only if its outcome is `no_answer`.

Facts and answers are compared after `sanad.text.arabic.normalize_for_search`, which also
applies `normalize_number_tokens`: diacritics, tatweel and alef forms fold away, Arabic-Indic
digits become Latin, and thousands separators go, so "1,840", "1840" and 1,840 written in
Arabic-Indic digits with the Arabic separator are one number. A numeric fact matches only as
a whole number: "538" is not in "1538" or "5.538", and "43" is not in "43.4". A text fact
matches as a substring, so a name still matches with a clitic in front of it ("لليلى الزين"
holds "ليلى الزين").

Each failure gets exactly one category, the first that applies:
1. `error`: the request failed, or the server ended in `outcome: error`. Not a scoring
   verdict: the item counts as wrong, and the run is flagged.
2. `invented_answer`: an unanswerable item was answered (`low_confidence` included). The
   worst failure: it is what the refusal gate exists to prevent.
3. `page_split`: a `page_split: true` item failed, whatever the cause.
4. `false_refusal`: an answerable item was refused. The row keeps `refusal_reason` and band.
5. `retrieval`: no expected page among the candidates.
6. `generation`: an expected page was among the candidates, but the facts or the citation
   are wrong.
7. `unclassified`: as 5 or 6, but the server sent no candidates (no diagnostics), so the two
   can't be told apart.

Every row also records the secondary facts (missing facts, citation match, best rank of an
expected page), so a failure can be explained whatever its category.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from sanad.eval.questions import Question
from sanad.text.arabic import normalize_for_search

Category = Literal[
    "error",
    "invented_answer",
    "page_split",
    "false_refusal",
    "retrieval",
    "generation",
    "unclassified",
]
CATEGORIES: tuple[Category, ...] = (
    "error",
    "invented_answer",
    "page_split",
    "false_refusal",
    "retrieval",
    "generation",
    "unclassified",
)
ANSWERED_OUTCOMES = frozenset({"answered", "low_confidence"})
OUTCOMES = frozenset({"answered", "low_confidence", "no_answer", "error"})

# Citation markers as the answer carries them: [1], [2, 3], [٢]. Stripped before matching, so
# a marker can't pass for a numeric fact.
_MARKER_RE = re.compile(r"\[\s*\d+(?:\s*[,\N{ARABIC COMMA}]\s*\d+)*\s*\]")
# A fact that is a number once normalised: 538, 1840 (from "1,840"), 43.4, 82%.
_NUMBER_FACT_RE = re.compile(r"\d+(?:\.\d+)?%?")


@dataclass(frozen=True)
class CandidatePage:
    """One reranked candidate from the diagnostics, resolved to its file."""

    rank: int  # 1 = best
    file: str | None  # None if the document id could not be resolved
    page: int | None
    score: float | None  # reranker score, 0..1
    dense_rank: int | None = None  # rank before fusion; None if that search missed it
    lexical_rank: int | None = None


@dataclass(frozen=True)
class Reply:
    """What the server answered for one question, with citations resolved to files."""

    outcome: str | None  # None when the request itself failed
    band: str | None = None
    refusal_reason: str | None = None
    answer: str | None = None
    cited: tuple[tuple[str | None, int], ...] = ()  # (file, page) in citation order
    candidates: tuple[CandidatePage, ...] | None = None  # None: no diagnostics
    error_code: str | None = None


@dataclass(frozen=True)
class ItemScore:
    correct: bool
    category: Category | None  # None when correct
    missing_facts: tuple[str, ...]
    citation_ok: bool
    retrieved: bool | None  # an expected page among the candidates; None if unknown
    expected_rank: int | None  # best rank of an expected page among the candidates


def matching_text(answer: str) -> str:
    """The answer as facts are matched against it: markers removed, then normalised."""
    return normalize_for_search(_MARKER_RE.sub(" ", answer))


def has_fact(normalized_answer: str, fact: str) -> bool:
    """`normalized_answer` comes from `matching_text`. Numbers match as whole numbers."""
    wanted = normalize_for_search(fact)
    if not wanted:
        return False
    if _NUMBER_FACT_RE.fullmatch(wanted):
        pattern = rf"(?<!\d)(?<!\d[.,]){re.escape(wanted)}(?!\d)(?![.,]\d)"
        return re.search(pattern, normalized_answer) is not None
    return wanted in normalized_answer


def missing_facts(answer: str | None, facts: Iterable[str]) -> tuple[str, ...]:
    text = matching_text(answer or "")
    return tuple(f for f in facts if not has_fact(text, f))


def best_expected_rank(
    candidates: Sequence[CandidatePage], expected: frozenset[tuple[str, int]]
) -> int | None:
    ranks = [c.rank for c in candidates if (c.file, c.page) in expected]
    return min(ranks) if ranks else None


def score_item(question: Question, reply: Reply) -> ItemScore:
    expected = question.expected_pages
    citation_ok = any(cite in expected for cite in reply.cited)
    if reply.candidates is None or not question.answerable:
        retrieved, rank = None, None
    else:
        rank = best_expected_rank(reply.candidates, expected)
        retrieved = rank is not None
    failed = reply.outcome is None or reply.outcome == "error" or reply.error_code is not None
    answered = not failed and reply.outcome in ANSWERED_OUTCOMES
    missing = missing_facts(reply.answer, question.must_include) if answered else ()

    if failed:
        correct = False
    elif question.answerable:
        correct = answered and not missing and citation_ok
    else:
        correct = reply.outcome == "no_answer"

    category: Category | None = None
    if correct:
        pass
    elif failed:
        category = "error"
    elif not question.answerable:
        category = "invented_answer"
    elif question.page_split:
        category = "page_split"
    elif not answered:
        category = "false_refusal"
    elif retrieved is None:
        category = "unclassified"
    else:
        category = "generation" if retrieved else "retrieval"
    return ItemScore(
        correct=correct,
        category=category,
        missing_facts=missing,
        citation_ok=citation_ok,
        retrieved=retrieved,
        expected_rank=rank,
    )
