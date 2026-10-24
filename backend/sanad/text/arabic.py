"""Arabic text handling: the one place where Arabic is cleaned, normalised and matched.

CLAUDE.md non-negotiable 5: ingestion cleaning, the lexical index, query terms and eval
scoring all go through this module, and no other code writes its own regexes for
diacritics, alef, hamza or tatweel. Everything here is a pure function with no I/O.

The two kinds of output make different promises:
- `clean_extracted` produces *display* text (stored pages, snippets, citations). It only
  repairs what PDF extraction broke. Case, digits, codes such as YEP-2021-03 and URLs stay
  byte-exact.
- `normalize_for_search` produces *matching* text (the lexical index, query terms, eval
  facts). It is lossy on purpose: no diacritics, one alef, Latin digits, lower case. Codes
  and URLs survive as one contiguous token each, lower-cased.

Single characters are written as \\N{...} escapes: they document themselves, and ruff's
confusable-character rules (RUF001-003) would flag a bare alef or heh.
"""

import re
import unicodedata
from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Literal

__all__ = [
    "ALEF",
    "ALEF_MAKSURA",
    "ARABIC_SHARE_FOR_AR",
    "ARABIC_SHARE_FOR_EN",
    "ARABIC_STOPWORDS",
    "ENGLISH_STOPWORDS",
    "HEH",
    "RUNNING_LINE_EDGE",
    "RUNNING_LINE_MIN_PAGES",
    "TATWEEL",
    "TEH_MARBUTA",
    "VISUAL_ORDER_MARGIN",
    "VISUAL_ORDER_MIN_EVIDENCE",
    "WAW",
    "YEH",
    "LanguageCode",
    "clean_extracted",
    "detect_language",
    "is_visual_order",
    "lexical_terms",
    "normalize_for_search",
    "normalize_number_tokens",
    "repair_visual_order",
    "search_tokens",
    "sentence_spans",
    "split_sentences",
    "strip_clitics",
]

LanguageCode = Literal["ar", "en", "mixed"]

# --- characters ---------------------------------------------------------------------------

ALEF = "\N{ARABIC LETTER ALEF}"
YEH = "\N{ARABIC LETTER YEH}"
WAW = "\N{ARABIC LETTER WAW}"
HEH = "\N{ARABIC LETTER HEH}"
TEH_MARBUTA = "\N{ARABIC LETTER TEH MARBUTA}"
ALEF_MAKSURA = "\N{ARABIC LETTER ALEF MAKSURA}"
TATWEEL = "\N{ARABIC TATWEEL}"

# Harakat, tanween, shadda and sukun (U+064B-U+0652), the rest of the combining block
# (maddah, hamza above and below, rarer marks: U+0653-U+065F) and the superscript alef.
# The extra marks only survive NFKC where they don't compose with their base letter.
_TASHKEEL = "".join(map(chr, range(0x064B, 0x0660))) + "\N{ARABIC LETTER SUPERSCRIPT ALEF}"

_BIDI_CONTROLS = (
    "\N{ARABIC LETTER MARK}"
    "\N{LEFT-TO-RIGHT MARK}\N{RIGHT-TO-LEFT MARK}"
    "\N{LEFT-TO-RIGHT EMBEDDING}\N{RIGHT-TO-LEFT EMBEDDING}\N{POP DIRECTIONAL FORMATTING}"
    "\N{LEFT-TO-RIGHT OVERRIDE}\N{RIGHT-TO-LEFT OVERRIDE}"
    "\N{LEFT-TO-RIGHT ISOLATE}\N{RIGHT-TO-LEFT ISOLATE}\N{FIRST STRONG ISOLATE}"
    "\N{POP DIRECTIONAL ISOLATE}"
    # A byte-order mark, or a zero-width no-break space mid-text. NFKC leaves it alone.
    "\N{ZERO WIDTH NO-BREAK SPACE}"
)
# Invisible characters that split a word for matching purposes but carry no meaning.
_ZERO_WIDTH = (
    "\N{SOFT HYPHEN}\N{ZERO WIDTH SPACE}\N{ZERO WIDTH NON-JOINER}\N{ZERO WIDTH JOINER}"
    "\N{WORD JOINER}"
)

_LETTER_MAP = {
    "\N{ARABIC LETTER ALEF WITH HAMZA ABOVE}": ALEF,
    "\N{ARABIC LETTER ALEF WITH HAMZA BELOW}": ALEF,
    "\N{ARABIC LETTER ALEF WITH MADDA ABOVE}": ALEF,
    "\N{ARABIC LETTER ALEF WASLA}": ALEF,
    ALEF_MAKSURA: YEH,
    "\N{ARABIC LETTER WAW WITH HAMZA ABOVE}": WAW,
    "\N{ARABIC LETTER YEH WITH HAMZA ABOVE}": YEH,
    # Text typed on a Persian keyboard layout uses these code points for yeh and kaf.
    "\N{ARABIC LETTER FARSI YEH}": YEH,
    "\N{ARABIC LETTER KEHEH}": "\N{ARABIC LETTER KAF}",
}

_NUMBER_TABLE: dict[int, str | None] = {
    **{0x0660 + d: str(d) for d in range(10)},  # Arabic-Indic digits
    **{0x06F0 + d: str(d) for d in range(10)},  # Extended Arabic-Indic (Persian) digits
    ord("\N{ARABIC DECIMAL SEPARATOR}"): ".",
    ord("\N{ARABIC PERCENT SIGN}"): "%",
}

_MARKS_TABLE: dict[int, str | None] = {ord(c): None for c in _TASHKEEL + TATWEEL}
_BIDI_TABLE: dict[int, str | None] = {ord(c): None for c in _BIDI_CONTROLS}
_INVISIBLE_TABLE: dict[int, str | None] = {ord(c): None for c in _BIDI_CONTROLS + _ZERO_WIDTH}
_SEARCH_TABLE: dict[int, str | None] = {
    **_MARKS_TABLE,
    **{ord(k): v for k, v in _LETTER_MAP.items()},
    **_NUMBER_TABLE,
    ord("\N{ARABIC THOUSANDS SEPARATOR}"): ",",
}
_SEARCH_TABLE_TAA: dict[int, str | None] = {**_SEARCH_TABLE, ord(TEH_MARBUTA): HEH}
_LEFT_GUILLEMET = "\N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}"
_RIGHT_GUILLEMET = "\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}"
_MIRRORED = str.maketrans(
    "()[]{}<>" + _LEFT_GUILLEMET + _RIGHT_GUILLEMET, ")(][}{><" + _RIGHT_GUILLEMET + _LEFT_GUILLEMET
)


def _build_presentation_fold() -> dict[int, str | None]:
    """Map every compatibility character in U+FB50-U+FEFE to its NFKC form.

    That covers the Arabic presentation forms (positional letter shapes and ligatures such
    as lam-alef) and the small and vertical punctuation forms between them. Harakat forms
    (U+FE70-U+FE7F) decompose to a space or tatweel plus the mark; only the mark is kept,
    so a stray space can't split the word it sat on.
    """
    table: dict[int, str | None] = {}
    for code in range(0xFB50, 0xFEFF):
        folded = unicodedata.normalize("NFKC", chr(code))
        if 0xFE70 <= code <= 0xFE7F:
            folded = folded.lstrip(" " + TATWEEL)
        if folded != chr(code):
            table[code] = folded
    return table


def _presentation_forms(shape: str) -> frozenset[str]:
    names = ((chr(code), unicodedata.name(chr(code), "")) for code in range(0xFB50, 0xFEFF))
    return frozenset(char for char, name in names if name.endswith(shape))


_PRESENTATION_FOLD = _build_presentation_fold()
_INITIAL_FORMS = _presentation_forms("INITIAL FORM")
_FINAL_FORMS = _presentation_forms("FINAL FORM")

# --- character classes for regexes --------------------------------------------------------

_ARABIC_BLOCKS = r"\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff"
# Arabic letters as they appear after normalisation: no marks, no tatweel, no digits.
_AR_LETTERS = (
    r"\u0621-\u063f\u0641-\u064a\u066e\u066f\u0671-\u06d3\u06d5\u06ee\u06ef\u06fa-\u06fc"
    r"\u06ff\u0750-\u077f\u08a0-\u08ff"
)
# A letter of any script other than Arabic (Latin, in practice).
_OTHER_LETTER = rf"[^\W\d_{_ARABIC_BLOCKS}]"
# A letter, digit or mark of any script other than Arabic.
_OTHER_ALNUM = rf"[^\W_{_ARABIC_BLOCKS}]"

_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_URL_SPLIT_RE = re.compile(rf"({_URL_RE.pattern})", re.IGNORECASE)
_URL_TRAILING = (
    ".,;:!?)]}\"'"
    + _RIGHT_GUILLEMET
    + "\N{ARABIC QUESTION MARK}\N{ARABIC COMMA}\N{ARABIC SEMICOLON}"
)
_ARABIC_SCRIPT_RE = re.compile(rf"[{_ARABIC_BLOCKS}]")
_LETTER_DIGIT_RE = re.compile(rf"(?<=[{_AR_LETTERS}])(?=\d)|(?<=\d)(?=[{_AR_LETTERS}])")

# --- numbers ------------------------------------------------------------------------------

# A number written with thousands separators: comma, Arabic thousands separator, thin space
# or narrow no-break space, each followed by exactly three digits.
_GROUPED_NUMBER_RE = re.compile(r"(?<!\d)\d{1,3}(?:[,\u066c\u2009\u202f]\d{3})+(?!\d)")
_GROUP_SEPARATOR_RE = re.compile(r"[,\u066c\u2009\u202f]")
# A percent sign goes with the number it touches; one spaced off on both sides goes with
# the number before it ("52 %"), unless a number follows it ("2021 % 52" is a flipped "52%").
_PERCENT_AFTER_RE = re.compile(r"(\d)[^\S\n]+%(?![^\S\n]*\d)")
_PERCENT_BEFORE_RE = re.compile(r"(?<![\d.%])%[^\S\n]*(\d+(?:\.\d+)?)(?![\d%])")


def normalize_number_tokens(text: str) -> str:
    """Write every number one way, so eval scoring can compare them as strings.

    - Arabic-Indic and Persian digits become Latin digits.
    - Thousands separators (`,` U+066C, thin space, narrow no-break space) are removed, but
      only inside a properly grouped number: "1,250" becomes "1250", while "2019, 2020"
      and "1,25" are left alone.
    - The Arabic decimal separator becomes ".".
    - A percent sign on either side ("52%", "52 %", "%52", Arabic percent) becomes a "%"
      directly after the number: "52%". RTL extraction flips the sign's side, which is
      why the eval files store percentages as bare numbers.

    URLs are left untouched. Everything else (letters, case, spacing) is unchanged.
    """
    return _outside_urls(text, _normalize_numbers)


def _normalize_numbers(text: str) -> str:
    text = text.translate(_NUMBER_TABLE)
    text = _GROUPED_NUMBER_RE.sub(lambda m: _GROUP_SEPARATOR_RE.sub("", m.group()), text)
    text = _PERCENT_AFTER_RE.sub(r"\1%", text)
    return _PERCENT_BEFORE_RE.sub(r"\1%", text)


def _outside_urls(text: str, transform: Callable[[str], str]) -> str:
    parts = _URL_SPLIT_RE.split(text)  # URLs land on the odd indexes
    return "".join(part if i % 2 else transform(part) for i, part in enumerate(parts))


# --- search normalisation -----------------------------------------------------------------


def normalize_for_search(text: str, *, fold_taa_marbuta: bool = True) -> str:
    """Normalise text for matching: the lexical index, query terms and eval facts.

    In order:
    1. Fold presentation forms and drop invisible characters (bidi controls, zero-width
       characters, soft hyphen): a query pasted from Word may carry a right-to-left mark.
    2. Normalise number tokens (`normalize_number_tokens`). This runs before NFKC, which
       would turn a thin-space thousands separator into an ordinary space.
    3. NFKC. It also composes a decomposed alef + hamza into one letter, for step 4.
    4. Strip tashkeel and tatweel. Unify alef forms to bare alef, alef maqsura to yeh,
       waw-hamza to waw, yeh-hamza to yeh and, if `fold_taa_marbuta` (the default), teh
       marbuta to heh. Persian yeh and keheh become Arabic yeh and kaf.
    5. Put a space between an Arabic letter and a digit ("2023" inside "and 2023"), so the
       number matches on its own. URLs are exempt.
    6. Lower-case, and collapse all whitespace (newlines included) to single spaces.

    Index and query must use the same `fold_taa_marbuta` value.
    """
    text = text.translate(_PRESENTATION_FOLD).translate(_INVISIBLE_TABLE)
    text = unicodedata.normalize("NFKC", normalize_number_tokens(text))
    text = text.translate(_SEARCH_TABLE_TAA if fold_taa_marbuta else _SEARCH_TABLE)
    text = _outside_urls(text, lambda part: _LETTER_DIGIT_RE.sub(" ", part))
    return " ".join(text.lower().split())


# --- stopwords and lexical terms ----------------------------------------------------------

# Written in ordinary spelling; ARABIC_STOPWORDS holds their normalised forms. Note that
# normalisation makes "على" (on) identical to the name "علي" (Ali), so a question about
# someone called Ali loses that term from the lexical query (dense retrieval still has it).
_ARABIC_STOPWORD_SOURCE = (
    # prepositions
    "في من إلى على عن مع حتى منذ مذ لدى عند نحو حول دون بين خلال ضمن عبر قبل بعد فوق تحت "
    "أمام وراء سوى غير بلا ضد عدا حسب بحسب وفق وفقا طبقا مثل "
    # prepositions with a pronoun suffix
    "فيه فيها فيهم فيهما منه منها منهم منهما عنه عنها عنهم عليه عليها عليهم إليه إليها "
    "إليهم له لها لهم لهما لنا لي لك لكم به بها بهم بهما معه معها معهم معنا بينهم بينها "
    "بينهما عنده عندها عندهم لديه لديها لديهم لدينا "
    # conjunctions and particles
    "أو أم ثم بل لكن إن أن كأن لأن لأنه لأنها كي لكي حيث إذ إذا إذن لو لولا لا لم لن "
    "ما قد لقد سوف إلا أما إما كما مما ممن عما بما فيما بينما كلما عندما حين حينما "
    # question words
    "هل كم كيف متى أين لماذا ماذا أي أية "
    # pronouns, demonstratives, relatives
    "أنا نحن أنت أنتم أنتن هو هي هم هما هن هذا هذه هذان هاتان هؤلاء ذلك تلك ذاك أولئك "
    "هنا هناك هنالك الذي التي الذين اللذان اللتان اللواتي اللاتي اللائي "
    # auxiliaries
    "كان كانت كانوا يكون تكون يكن ليس ليست ليسوا صار أصبح أصبحت ظل مازال لايزال تم يتم "
    # quantifiers and adverbs
    "كل بعض جميع كلا كلتا عدة أيضا فقط جدا ذات ذو نفس لذلك كذلك لهذا بذلك بهذا هكذا ثمة "
    "الآن"
)
# Words that also appear with the conjunction wa- or fa- attached ("وفي", "فإن").
_ARABIC_CONJUNCTION_HOSTS = (
    "في من إلى على عن مع ما لا لم لن قد هو هي هم هذا هذه ذلك تلك كان كانت التي الذي "
    "الذين إن أن بين كل بعد قبل خلال عند حتى إذا لكن"
)
_CONJUNCTIONS = (WAW, "\N{ARABIC LETTER FEH}")

ARABIC_STOPWORDS: frozenset[str] = frozenset(
    normalize_for_search(_ARABIC_STOPWORD_SOURCE).split()
) | frozenset(
    c + w for w in normalize_for_search(_ARABIC_CONJUNCTION_HOSTS).split() for c in _CONJUNCTIONS
)

_ENGLISH_STOPWORD_SOURCE = (
    "a about above according actually after again against all also am an and any "
    "approximately are as at be because been before being below between both but by can "
    "could did do does doing done down during each either few for from further get got "
    "had has have having he her here hers him his how i if in into is it its itself just "
    "many may me might more most much must my no nor not now of off on once only or other "
    "our ours out over own per roughly same shall she should so some such than that the "
    "their theirs them then there these they this those through to too under until up "
    "upon us very was we were what when where whether which while who whom whose why will "
    "with within without would you your yours"
)
ENGLISH_STOPWORDS: frozenset[str] = frozenset(_ENGLISH_STOPWORD_SOURCE.split())

_TOKEN_RE = re.compile(
    rf"{_URL_RE.pattern}"
    rf"|[{_AR_LETTERS}]+"
    # Latin words, numbers and codes, with inner punctuation kept: yep-2021-03, 12.5
    rf"|{_OTHER_ALNUM}+(?:[-./:@+&_]{_OTHER_ALNUM}+)*"
)


def search_tokens(text: str, *, fold_taa_marbuta: bool = True) -> list[str]:
    """Split `normalize_for_search(text)` into tokens, punctuation dropped.

    Arabic words, Latin words, numbers (12.5), codes (yep-2021-03) and URLs each come out
    as one token. Stopwords are kept; `lexical_terms` removes them. A run of Arabic letters
    is always its own token, so "و2023" gives "و" and "2023".
    """
    normalised = normalize_for_search(text, fold_taa_marbuta=fold_taa_marbuta)
    return [m.group().rstrip(_URL_TRAILING) for m in _TOKEN_RE.finditer(normalised)]


def lexical_terms(
    question: str, *, fold_taa_marbuta: bool = True, clitics: bool = False
) -> list[str]:
    """The content terms of a question, for the OR lexical query (SYSTEM_DESIGN section 6).

    Tokens of the normalised question, minus Arabic and English stopwords and single
    letters (single digits are kept), deduplicated in first-seen order. Works the same for
    Arabic, English and mixed questions.

    `clitics=True` is the E2 sweep variant: each term also goes through `strip_clitics`.
    The index side must then get the same treatment, e.g. by indexing
    `" ".join(strip_clitics(t) for t in search_tokens(text))`.
    """
    terms: list[str] = []
    for token in search_tokens(question, fold_taa_marbuta=fold_taa_marbuta):
        if _is_stopword(token):
            continue
        if clitics:
            token = strip_clitics(token)
            if _is_stopword(token):
                continue
        if (len(token) > 1 or token.isdigit()) and token not in terms:
            terms.append(token)
    return terms


def _is_stopword(token: str) -> bool:
    return token.replace(TEH_MARBUTA, HEH) in ARABIC_STOPWORDS or token in ENGLISH_STOPWORDS


# Longest first. A lone conjunction or preposition (و ف ب ل) is only stripped together
# with the article: too many words start with those letters themselves (وادي, برنامج,
# لجنة, فريق).
_CLITIC_PREFIXES = ("وبال", "فبال", "وال", "فال", "بال", "ولل", "فلل", "لل", "ال")
_MIN_STEM = 2


def strip_clitics(token: str) -> str:
    """Strip a leading article, with any conjunction or preposition in front of it.

    Conservative light stemming, for the E2 sweep only. It expects a normalised token
    (`search_tokens` output): "وبالمشروع" and "للتعليم" become "مشروع" and "تعليم". It never
    leaves fewer than two letters, so "الف" (from "ألف") stays whole, and a token that
    doesn't start with one of the prefixes comes back unchanged.
    """
    for prefix in _CLITIC_PREFIXES:
        if token.startswith(prefix) and len(token) - len(prefix) >= _MIN_STEM:
            return token[len(prefix) :]
    return token


# --- language -----------------------------------------------------------------------------

# Share of Arabic letters among all letters. Digits, punctuation and URLs don't count, so
# an Arabic question with a code such as YEP-2021-03 in it is still "ar".
ARABIC_SHARE_FOR_AR = 0.8
ARABIC_SHARE_FOR_EN = 0.2


def detect_language(text: str) -> LanguageCode:
    """Classify text as "ar", "en" or "mixed" by the share of Arabic letters.

    - "ar" when at least ARABIC_SHARE_FOR_AR (80%) of the letters are Arabic.
    - "en" when at most ARABIC_SHARE_FOR_EN (20%) are; "en" means any non-Arabic script.
    - "mixed" in between, and also for text with no letters at all (a page of figures, a
      question that is only a number), where there is no evidence either way and callers
      should fall back to the interface language.

    Letters inside URLs aren't counted.
    """
    arabic = other = 0
    for char in _URL_RE.sub(" ", text):
        if not char.isalpha() or char == TATWEEL:
            continue
        if _ARABIC_SCRIPT_RE.match(char):
            arabic += 1
        else:
            other += 1
    if arabic + other == 0:
        return "mixed"
    share = arabic / (arabic + other)
    if share >= ARABIC_SHARE_FOR_AR:
        return "ar"
    if share <= ARABIC_SHARE_FOR_EN:
        return "en"
    return "mixed"


# --- sentences ----------------------------------------------------------------------------

_ARABIC_STOPS = frozenset("\N{ARABIC QUESTION MARK}\N{ARABIC COMMA}\N{ARABIC SEMICOLON}")
_SENTENCE_BREAK_RE = re.compile(
    # a run of terminators, with any closing quotes or brackets after it
    r"(?P<stop>[.!?\u061f\u060c\u061b]+[\"'\u00bb\u201d\u2019)\]]*)"
    # or a blank line
    r"|(?P<para>\n[^\S\n]*\n\s*)"
)
# A single letter right before the full stop, with no word character before it.
_INITIAL_BEFORE_RE = re.compile(r"(?<!\w)[^\W\d_]$")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences (or clauses, at the Arabic comma). See `sentence_spans`."""
    return [text[start:end] for start, end in sentence_spans(text)]


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) offsets of each sentence, trimmed of surrounding whitespace.

    Boundaries (DECISIONS D1: Arabic sentence boundaries include ؟ ، ؛):
    - `؟ ، ؛` always end a sentence.
    - `. ! ?` end one only when followed by whitespace or the end of the text. So decimals
      (12.5), URLs (example.org/r?id=7) and codes are never split.
    - A full stop after a single letter is an initial or an abbreviation (د. سامي, J. Smith)
      and doesn't end a sentence.
    - A blank line always ends one. A single newline is just a wrapped line.

    The terminator and any closing quote or bracket stay with their sentence.
    """
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _SENTENCE_BREAK_RE.finditer(text):
        if match.lastgroup == "para":
            end, next_start = match.start(), match.end()
        elif _ends_sentence(text, match):
            end = next_start = match.end()
        else:
            continue
        _add_span(spans, text, start, end)
        start = next_start
    _add_span(spans, text, start, len(text))
    return spans


def _ends_sentence(text: str, match: re.Match[str]) -> bool:
    stops = match.group("stop")
    if _ARABIC_STOPS.intersection(stops):
        return True
    if match.end() < len(text) and not text[match.end()].isspace():
        return False
    if stops != ".":
        return True
    return _INITIAL_BEFORE_RE.search(text, max(0, match.start() - 1), match.start()) is None


def _add_span(spans: list[tuple[int, int]], text: str, start: int, end: int) -> None:
    chunk = text[start:end]
    stripped = chunk.strip()
    if stripped:
        start += len(chunk) - len(chunk.lstrip())
        spans.append((start, start + len(stripped)))


# --- visual-order repair ------------------------------------------------------------------

# Evidence needed before a line is treated as visual order: the reversed line must score
# at least VISUAL_ORDER_MIN_EVIDENCE and more than VISUAL_ORDER_MARGIN times the line as
# stored. See `is_visual_order`.
VISUAL_ORDER_MIN_EVIDENCE = 2
VISUAL_ORDER_MARGIN = 3

# Runs that the bidi algorithm displays left to right inside an Arabic line, and that a
# visual-order extractor therefore stores in their natural order:
# - a Latin run, from a Latin letter to the last Latin letter or digit before the next
#   Arabic letter, spaces and punctuation included: "Save the Children", "UNICEF 2021",
#   "YEP-2021-03", "https://example.org/r?id=7"
# - a number: digits joined by single separators, with a percent or currency sign on
#   either side: "1,250", "12.5", "2021-03-15", "52%". Two numbers with a space between
#   them are two runs, because the space takes the Arabic direction.
_NUMBER_SIGN = r"[%#$\N{ARABIC PERCENT SIGN}\N{POUND SIGN}\N{EURO SIGN}]"
_NUMBER_JOINER = r"[-+,./:\N{ARABIC DECIMAL SEPARATOR}\N{ARABIC THOUSANDS SEPARATOR}]"
_LTR_RUN_RE = re.compile(
    rf"({_OTHER_LETTER}(?:[^\w{_ARABIC_BLOCKS}]*{_OTHER_ALNUM})*{_NUMBER_SIGN}?"
    rf"|{_NUMBER_SIGN}?\d+(?:{_NUMBER_JOINER}\d+)*{_NUMBER_SIGN}?)"
)
# An Arabic word as extracted: letters, marks, tatweel and presentation forms.
_RAW_ARABIC_WORD_RE = re.compile(r"[\u0621-\u065f\u0670-\u06d3\u06d5\ufb50-\ufdff\ufe70-\ufefc]+")
_ARTICLE = ALEF + "\N{ARABIC LETTER LAM}"
_WORD_FINAL_ONLY = (TEH_MARBUTA, ALEF_MAKSURA)


def is_visual_order(line: str) -> bool:
    """Guess whether an extracted line is in visual (reversed) order. Conservative.

    Some PDF extractors emit glyphs left to right as displayed, so Arabic comes out
    reversed while Latin words and numbers keep their natural order. The line is scored as
    stored and as `repair_visual_order` would rewrite it; each Arabic word scores a point
    for each sign that it reads in logical order:
    - starts with an initial presentation form, or ends with a final one (strongest)
    - ends with teh marbuta or alef maqsura, which never start a word
    - starts with the article (al-), at four letters or more
    - is a stopword

    The line counts as reversed only when the rewritten line scores at least
    VISUAL_ORDER_MIN_EVIDENCE and more than VISUAL_ORDER_MARGIN times the stored line.
    Lines without that evidence (short ones included) are left as they are.

    To extend: add cases under backend/tests/text/ (the S1 extraction spike will supply
    real ones), then adjust the scoring or the two thresholds here.
    """
    return _visual_candidate(line) is not None


def repair_visual_order(line: str) -> str:
    """Return the line in logical order if `is_visual_order` says it is reversed.

    The repair reverses the order of the runs in the line, and the characters inside the
    Arabic runs, mirroring brackets. Latin and digit runs (YEP-2021-03, 1,250, URLs) keep
    their characters as they are. Run this on the line as extracted, before presentation
    forms are folded: a lam-alef ligature is one glyph, which only folds into the right
    two letters after the reversal.

    Assumptions still to be checked against the S1 cases: brackets come out with their
    displayed (mirrored) shape, and combining marks follow their letter.
    """
    candidate = _visual_candidate(line)
    return line if candidate is None else candidate


def _visual_candidate(line: str) -> str | None:
    candidate = _reverse_runs(line)
    reversed_score = _logical_evidence(candidate)
    if reversed_score < VISUAL_ORDER_MIN_EVIDENCE:
        return None
    if reversed_score <= VISUAL_ORDER_MARGIN * _logical_evidence(line):
        return None
    return candidate


def _reverse_runs(line: str) -> str:
    parts = _LTR_RUN_RE.split(line)  # left-to-right runs land on the odd indexes
    return "".join(
        part if i % 2 else part[::-1].translate(_MIRRORED)
        for i, part in reversed(list(enumerate(parts)))
    )


def _logical_evidence(line: str) -> int:
    score = 0
    for match in _RAW_ARABIC_WORD_RE.finditer(line):
        raw = match.group()
        score += (raw[0] in _INITIAL_FORMS) + (raw[-1] in _FINAL_FORMS)
        word = raw.translate(_PRESENTATION_FOLD).translate(_MARKS_TABLE)
        if len(word) < 2:
            continue
        score += word.endswith(_WORD_FINAL_ONLY)
        score += len(word) >= 4 and word.startswith(_ARTICLE)
        score += word.translate(_SEARCH_TABLE_TAA) in ARABIC_STOPWORDS
    return score


# --- cleaning extracted pages -------------------------------------------------------------

# Running headers and footers: a line is one if it sits among the first or last
# RUNNING_LINE_EDGE non-blank lines of its page, and the same line (after normalisation,
# digits masked) sits there on more than half of the pages that have text. Documents with
# fewer than RUNNING_LINE_MIN_PAGES such pages are never touched, or a one-page document
# would lose every line.
RUNNING_LINE_EDGE = 3
RUNNING_LINE_MIN_PAGES = 3

_DIGIT_RUN_RE = re.compile(r"\d+")


def clean_extracted(pages: Sequence[str]) -> list[str]:
    """Clean the per-page text of an extracted PDF for storage and display.

    Per line: remove bidi controls and byte-order marks, repair visual order
    (`repair_visual_order`), fold presentation forms (lam-alef and other ligatures
    included), compose with NFC, and collapse whitespace. Then remove running headers,
    footers and page numbers (see RUNNING_LINE_EDGE), and collapse blank lines so that
    paragraphs stay separated by exactly one.

    Only presentation forms are folded, not full NFKC: footnote superscripts and the like
    stay as printed. `normalize_for_search` applies NFKC on the search side.

    Returns exactly one string per input page, empty pages included: the list index is the
    page number that citations point to.
    """
    lines = [[_clean_line(line) for line in page.splitlines()] for page in pages]
    return ["\n".join(_collapse_blank(page)) for page in _drop_running_lines(lines)]


def _clean_line(line: str) -> str:
    line = repair_visual_order(line.translate(_BIDI_TABLE))
    line = unicodedata.normalize("NFC", line.translate(_PRESENTATION_FOLD))
    return " ".join(line.split())


def _collapse_blank(lines: list[str]) -> list[str]:
    kept: list[str] = []
    for line in lines:
        if line or (kept and kept[-1]):
            kept.append(line)
    if kept and not kept[-1]:
        kept.pop()
    return kept


def _drop_running_lines(pages: list[list[str]]) -> list[list[str]]:
    with_text = [i for i, page in enumerate(pages) if any(page)]
    if len(with_text) < RUNNING_LINE_MIN_PAGES:
        return pages
    edge_keys = {
        i: {j: _running_key(pages[i][j]) for j in _edge_lines(pages[i])} for i in with_text
    }
    seen: defaultdict[str, defaultdict[int, set[tuple[int, ...]]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for i, keys in edge_keys.items():
        for key, numbers in keys.values():
            seen[key][i].add(numbers)
    # The numbers of each running line, page by page. A page where one key masks lines with
    # different numbers (a page number "3" and a table cell "790") is ambiguous: it neither
    # counts nor loses a line for that key.
    running: dict[tuple[str, int], tuple[int, ...]] = {}
    for key, by_page in seen.items():
        numbers_by_page = {i: next(iter(n)) for i, n in by_page.items() if len(n) == 1}
        if 2 * len(numbers_by_page) > len(with_text) and _numbers_track_pages(numbers_by_page):
            running |= {(key, i): numbers for i, numbers in numbers_by_page.items()}
    return [
        [
            line
            for j, line in enumerate(page)
            if j not in edge_keys.get(i, {})
            or running.get((edge_keys[i][j][0], i)) != edge_keys[i][j][1]
        ]
        for i, page in enumerate(pages)
    ]


def _edge_lines(page: list[str]) -> set[int]:
    filled = [j for j, line in enumerate(page) if line]
    return set(filled[:RUNNING_LINE_EDGE]) | set(filled[-RUNNING_LINE_EDGE:])


def _running_key(line: str) -> tuple[str, tuple[int, ...]]:
    normalised = normalize_for_search(line)
    numbers = tuple(int(n) for n in _DIGIT_RUN_RE.findall(normalised))
    return _DIGIT_RUN_RE.sub("#", normalised), numbers


def _numbers_track_pages(numbers_by_page: dict[int, tuple[int, ...]]) -> bool:
    """True if each masked number is the same on every page, or is the page number.

    "التقرير السنوي 2021" repeats 2021; "صفحة 3 من 12" counts up with the page and repeats
    12. A table row ending every page with a different total does neither, so it stays.
    """
    pages = sorted(numbers_by_page)
    for column in zip(*(numbers_by_page[p] for p in pages), strict=True):
        constant = len(set(column)) == 1
        counts_pages = len({n - p for n, p in zip(column, pages, strict=True)}) == 1
        if not (constant or counts_pages):
            return False
    return True
