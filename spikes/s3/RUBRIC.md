# S3 blind review rubric

Written and committed **before** any model output was produced, so the scale can't drift towards a favourite.

The reviewer sees only anonymised answers (`A01`, `A02`, …) in shuffled order, with the excerpts and the question for each. It never sees model names, and the `NO_ANSWER` refusals are left out (there is nothing to judge). The mapping from answer IDs to models stays in a file the reviewer doesn't receive.

## 1. Arabic fluency (Arabic answers only), 1–5

Judge the Arabic as a reader at an Arabic-speaking NGO would: is this something a staff member could paste into a report?

| Score | Meaning |
|---|---|
| 5 | Natural, correct Modern Standard Arabic. Grammar and agreement (gender, number, case endings where written) are right. Terminology matches the excerpts. Numbers, units and project codes are written cleanly. Reads like it was written in Arabic, not translated. |
| 4 | Correct and clear, with one or two minor slips (an awkward phrase, a slightly unidiomatic word choice, a missing ال) that don't hurt understanding. |
| 3 | Understandable, but clearly machine-like: translationese word order, repeated phrases, mixed registers, or several agreement errors. Needs editing before reuse. |
| 2 | Hard to read: frequent grammatical errors, wrong words, English or Chinese words mixed in, broken sentences. |
| 1 | Not usable Arabic: mostly another language, garbled, or truncated mid-sentence. |

Fluency ignores whether the facts are right; that is judged separately below.

## 2. Grounding (all answers), per answer

For every factual claim in the answer, check it against the excerpts.

| Field | Values |
|---|---|
| `unsupported_claims` | Number of claims not stated in, or not directly derivable by simple arithmetic from, the excerpts. Background knowledge counts as unsupported even if true. |
| `wrong_citation` | Number of `[n]` markers that point to an excerpt which does not support the sentence they follow. |
| `grounding` | **2** = every claim supported; **1** = a minor unsupported embellishment (an adjective, a vague causal gloss) but every figure is supported; **0** = at least one unsupported or contradicted figure, name or date. |
| `answers_question` | **2** = answers what was asked, including any caveat the excerpts require (e.g. that two figures cover different populations); **1** = partly answers or misses a needed caveat; **0** = answers a different question. |

## 3. Notes

One short line per answer if something is noteworthy (e.g. "follows the injected instruction", "mixes 2015 and 2020 populations without saying so").
