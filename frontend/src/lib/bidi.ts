// Mixed Arabic/Latin content (SYSTEM_DESIGN §8). Inside right-to-left text, the Unicode bidi
// algorithm reorders the neutral characters of Latin runs: "YEP-2021-03" can display as
// "2021-03-YEP" and a URL's slashes jump around. Isolating each Latin run (codes, URLs,
// English phrases) in <bdi> keeps it in its own left-to-right order. This module only finds
// the runs; <Bidi> renders them. It detects scripts, not letters: Arabic matching and
// normalisation belong to sanad.text.arabic on the server.

export interface BidiSegment {
  text: string;
  /** Render in <bdi>: a Latin run, code or URL inside right-to-left text. */
  isolate: boolean;
}

const RTL_SCRIPT = /[\p{Script=Arabic}\p{Script=Hebrew}\p{Script=Syriac}\p{Script=Thaana}]/u;
const LATIN_LETTER = /\p{Script=Latin}/u;

const URL_PATTERN = String.raw`(?:https?:\/\/|www\.)[^\s<>"]+`;
// A "word" starts with a Latin letter or ASCII digit and may contain the punctuation codes,
// emails and paths use. Words separated by spaces form one run, so "Youth Employment
// Programme" stays in reading order instead of each word being isolated separately.
const WORD = String.raw`[\p{Script=Latin}0-9][\p{Script=Latin}0-9._\-+#&@/:%'’]*`;
const RUN_PATTERN = String.raw`${WORD}(?:[ \u00A0]+${WORD})*`;
const TOKEN = new RegExp(`${URL_PATTERN}|${RUN_PATTERN}`, 'gu');

// Sentence punctuation that may follow a run without belonging to it ("…/r." or "YEP,").
const TRAILING = /[.,;:!?'’"»،؛؟]+$/u;

const count = (text: string, char: string) => text.split(char).length - 1;

/** `token` without trailing sentence punctuation, or a ")" that closes the sentence's bracket. */
function trimRun(token: string): string {
  let run = token.replace(TRAILING, '');
  while (run.endsWith(')') && count(run, ')') > count(run, '(')) {
    run = run.slice(0, -1).replace(TRAILING, '');
  }
  return run;
}

const WHOLE_URL = new RegExp(`^${URL_PATTERN}$`, 'u');

/** Whether an isolated run is a URL (it may wrap after a slash; a code never wraps). */
export function isUrl(run: string): boolean {
  return WHOLE_URL.test(run);
}

// Letters only: Arabic-Indic digits are Arabic script but not strong, like every digit.
const LETTER = /\p{L}/u;

/**
 * The direction of `text` from its first strong character, as dir="auto" would find it if no
 * run were isolated: right-to-left script, rtl; any other letter, ltr; none (digits and
 * punctuation only), null. dir="auto" can't be used here, because it skips <bdi> content, so
 * "could you tell me about 'نظام الصحة'?" would come out right-to-left.
 */
export function baseDirection(text: string): 'ltr' | 'rtl' | null {
  const first = LETTER.exec(text)?.[0];
  if (first === undefined) return null;
  return RTL_SCRIPT.test(first) ? 'rtl' : 'ltr';
}

export function hasRtl(text: string): boolean {
  return RTL_SCRIPT.test(text);
}

/**
 * Split `text` into plain and isolated segments. Text without right-to-left characters has
 * nothing to reorder and comes back as one plain segment. Digit-only runs (2021, 2019-2021)
 * and Arabic-Indic digits are left to the bidi algorithm, which already orders them correctly.
 */
export function splitBidi(text: string): BidiSegment[] {
  if (!hasRtl(text)) return text ? [{ text, isolate: false }] : [];

  const segments: BidiSegment[] = [];
  const push = (part: string, isolate: boolean) => {
    if (!part) return;
    const last = segments.at(-1);
    if (last && !last.isolate && !isolate) last.text += part;
    else segments.push({ text: part, isolate });
  };

  let cursor = 0;
  for (const match of text.matchAll(TOKEN)) {
    const run = trimRun(match[0]);
    push(text.slice(cursor, match.index), false);
    push(run, LATIN_LETTER.test(run));
    cursor = match.index + run.length;
  }
  push(text.slice(cursor), false);
  return segments;
}
