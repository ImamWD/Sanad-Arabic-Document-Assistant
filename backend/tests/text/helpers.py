"""Builders for test input that lint won't accept as literals, and the seed corpus lines.

ruff's confusable-character rules flag some Arabic-Indic digits (they look like Latin
letters), so tests write Latin digits and convert them. Presentation forms are built from
their Unicode names, which also says exactly which glyph each one is.
"""

import unicodedata
from functools import cache
from pathlib import Path

SEED_SOURCES = Path(__file__).parents[3] / "seed" / "sources"


def arabic_indic(text: str) -> str:
    """Rewrite the Latin digits in `text` as Arabic-Indic digits."""
    return text.translate({ord(str(d)): chr(0x0660 + d) for d in range(10)})


def persian_digits(text: str) -> str:
    """Rewrite the Latin digits in `text` as Extended Arabic-Indic (Persian) digits."""
    return text.translate({ord(str(d)): chr(0x06F0 + d) for d in range(10)})


def shaped(*forms: str) -> str:
    """Presentation-form text from short names: "BEH INITIAL", "LIGATURE LAM WITH ALEF FINAL"."""
    names = (
        f"ARABIC {f} FORM" if f.startswith("LIGATURE") else f"ARABIC LETTER {f} FORM" for f in forms
    )
    return "".join(unicodedata.lookup(name) for name in names)


# "برنامج تمكين" and "الاستجابة" as a PDF stores them when it keeps positional glyphs.
BARNAMAJ = shaped(
    "BEH INITIAL", "REH FINAL", "NOON INITIAL", "ALEF FINAL", "MEEM INITIAL", "JEEM FINAL"
)
TAMKEEN = shaped("TEH INITIAL", "MEEM MEDIAL", "KAF MEDIAL", "YEH MEDIAL", "NOON FINAL")
ISTIJABA = shaped(
    "ALEF ISOLATED",
    "LIGATURE LAM WITH ALEF ISOLATED",
    "SEEN INITIAL",
    "TEH MEDIAL",
    "JEEM MEDIAL",
    "ALEF FINAL",
    "BEH INITIAL",
    "TEH MARBUTA FINAL",
)


@cache
def seed_lines() -> tuple[str, ...]:
    """Every non-blank line of the synthetic seed corpus (seed/sources/*.md)."""
    paths = sorted(SEED_SOURCES.glob("*.md"))
    assert paths, f"seed corpus not found under {SEED_SOURCES}"
    return tuple(
        line for p in paths for line in p.read_text(encoding="utf-8").splitlines() if line.strip()
    )
