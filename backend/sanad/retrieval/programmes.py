"""Programme names in a question: which programmes it names, by their distinctive words.

The reranker reads «نظام الصحة المجتمعية» ("the community health *system*") as off-topic for
passages about «برنامج الصحة المجتمعية» (the *programme*): the owner's question scored 0.009
and was refused at the gate, although the vector search had found the right pages (R1c). So
when a question names a programme, its official names are added to the rerank query.

A programme is named when the question holds its distinctive words, compared after
`sanad.text.arabic.lexical_terms` (normalised, stopwords and article clitics removed) and with
the generic heads (programme, project, initiative) left out:
- a name of one or two distinctive words: all of them, side by side, in order;
- a longer name: any two of its words, side by side in the question, in the name's order
  («بالمناطق الريفية» names the rural water project; «المناطق» alone does not).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from sanad.text.arabic import lexical_terms, normalize_for_search

# The generic head of a programme name says nothing about which programme it is.
GENERIC_HEADS = frozenset(
    normalize_for_search(word)
    for word in ("برنامج", "مشروع", "مبادرة", "programme", "program", "project", "initiative")
)
SHORT_NAME = 2


@dataclass(frozen=True)
class ProgrammeName:
    name_ar: str
    name_en: str


def _terms(text: str) -> list[str]:
    return [t for t in lexical_terms(text, clitics=True) if t not in GENERIC_HEADS]


def _adjacent_pairs(terms: Sequence[str]) -> set[tuple[str, str]]:
    return set(pairwise(terms))


def _names_it(question_terms: Sequence[str], name: str) -> bool:
    words = _terms(name)
    if not words:
        return False
    if len(words) <= SHORT_NAME:
        size = len(words)
        return any(
            list(question_terms[i : i + size]) == words
            for i in range(len(question_terms) - size + 1)
        )
    in_order = {(a, b) for i, a in enumerate(words) for b in words[i + 1 :]}
    return bool(_adjacent_pairs(question_terms) & in_order)


def named_programmes(question: str, programmes: Sequence[ProgrammeName]) -> list[ProgrammeName]:
    """The programmes `question` names, in the order given."""
    terms = _terms(question)
    return [p for p in programmes if _names_it(terms, p.name_ar) or _names_it(terms, p.name_en)]


def rerank_query(question: str, named: Sequence[ProgrammeName]) -> str:
    """The question, plus the official names of the programmes it names, for the reranker."""
    if not named:
        return question
    names = " | ".join(f"{p.name_ar} | {p.name_en}" for p in named)
    return f"{question}\n{names}"
