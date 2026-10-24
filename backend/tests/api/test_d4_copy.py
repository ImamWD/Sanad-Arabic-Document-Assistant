"""The approved D4 copy (docs/DECISIONS.md, accepted by the client) is pinned in both locales.

The refusal and the low-confidence banner were approved word for word, in both languages.
Changing them is a client decision: update DECISIONS.md first, then these constants.
F2 renders them from the `answer.refusal` and `answer.lowConfidence` keys.
"""

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]

REFUSAL = {
    "ar": "لم أجد في الوثائق المتاحة ما يجيب عن هذا السؤال.",
    "en": "I couldn't find an answer to this in the available documents.",
}
LOW_CONFIDENCE = {
    "ar": "هذه الإجابة مبنية على مصادر قد لا تتطابق تماماً مع سؤالك. راجع المصادر قبل الاعتماد عليها.",  # noqa: E501 (approved copy, kept on one line)
    "en": "This answer is based on sources that may not fully match your question. Check them before relying on it.",  # noqa: E501 (approved copy, kept on one line)
}


def _d4_section() -> str:
    text = (REPO / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    return text[text.index("## D4.") : text.index("## D5.")]


@pytest.mark.parametrize("copy", [*REFUSAL.values(), *LOW_CONFIDENCE.values()])
def test_pinned_copy_is_quoted_verbatim_in_decisions(copy: str) -> None:
    assert f'"{copy}"' in _d4_section()


@pytest.mark.parametrize("locale", ["ar", "en"])
def test_locales_carry_the_approved_copy(locale: str) -> None:
    path = REPO / "frontend" / "src" / "locales" / f"{locale}.json"
    messages = json.loads(path.read_text(encoding="utf-8"))
    assert messages["answer"]["refusal"] == REFUSAL[locale]
    assert messages["answer"]["lowConfidence"] == LOW_CONFIDENCE[locale]
