# E2: threshold tuning on the dev set

**Decision: `T_REFUSE` stays 0.15 and `T_CONFIDENT` stays 0.5.** The dev data gives no reason to move either one: every value in a wide range gives the same outcome, and the current values sit inside that range, on the cautious side. `RERANK_CANDIDATES` stays 30 (checked below, not changed).

Tuned on the dev set only (`eval/dev_questions.yaml`, version 3, 36 items). The headline set was not run or looked at.

## Setup

- Run: [`20261026T001804Z-dev-...-e2-0-baseline-t_refuse-0.15-t_confident-0.5.md`](20261026T001804Z-dev-sanad-gemma4-e4b-text-e2-0-baseline-t_refuse-0.15-t_confident-0.5.md), at commit `2016a25696d3` (`main` f0b7769 plus the D14 fix).
- Stack: the base `docker-compose.yml`, containerised Ollama (`sanad-gemma4-e4b-text`) on CPU, Apple M5, Docker VM with 16 GB, no other stack running. Generation was 23 tokens per second on a warm-up question before the run.
- No `LLM_UNAVAILABLE` and no timeout in the run.
- Reproduction: R1c's after run (`20261025T234149Z-...-r1c-after-programme-names`, already in `main`) has the same top score on all 36 items (no difference of 0.0005 or more) and the same outcome on every item.

## Baseline at 0.15 / 0.5

- Score: **33/36** (answerable 26/29)
- Unanswerable refused: 7/7. False refusals: 1 (D02). **Invented answers: 0.**
- recall@10: 29/29
- Outcomes: 20 answered (plain band), 7 low confidence (amber band), 9 refusals (4 by the gate, 5 by the model's `NO_ANSWER`)
- Latency, server total: median 32.6 s, p90 38.9 s. Rerank stage: median 5.8 s. Only D05 (7.6 s) reused Ollama's prompt cache, from the warm-up question.
- Failures: D02 (`false_refusal`, sentinel), D07 (`page_split`, sentinel), D32 (`generation`: an English question answered in Arabic)

## How the scores fall

The gate looks at the reranker's top score. The ml service turns the reranker's logit into 0..1 with a sigmoid, so 0.5 is the reranker's even-odds point.

| Group | n | Min | Median | Max |
|---|---|---|---|---|
| answerable, correct | 26 | 0.214 | 0.971 | 0.999 |
| answerable, failed | 3 | 0.488 | 0.995 | 0.999 |
| unanswerable | 7 | 0.002 | 0.015 | 0.954 |

Per item, by top score. The band and outcome are the same before and after, because the thresholds did not change.

| ID | Group | Top score | Band | Outcome | Refusal reason | Correct | Notes |
|---|---|---|---|---|---|---|---|
| D35 | unanswerable | 0.002 | refuse | no_answer | gate | yes | microfinance, colloquial |
| D36 | unanswerable | 0.004 | refuse | no_answer | gate | yes | microfinance, English |
| D20 | unanswerable | 0.006 | refuse | no_answer | gate | yes | |
| D30 | unanswerable | 0.015 | refuse | no_answer | gate | yes | highest gate refusal |
| D15 | answerable, correct | 0.214 | low_confidence | low_confidence | - | yes | lowest answerable; fully diacritised |
| D31 | answerable, correct | 0.235 | low_confidence | low_confidence | - | yes | the owner's question (0.009 before R1c) |
| D09 | answerable, correct | 0.272 | low_confidence | low_confidence | - | yes | English about an Arabic document |
| D06 | answerable, correct | 0.391 | low_confidence | low_confidence | - | yes | vocabulary shift |
| D22 | answerable, correct | 0.435 | low_confidence | low_confidence | - | yes | vocabulary shift |
| D16 | answerable, correct | 0.472 | low_confidence | low_confidence | - | yes | English about an Arabic document |
| D32 | answerable, failed | 0.488 | low_confidence | low_confidence | - | no | answer language (R1e) |
| D12 | answerable, correct | 0.577 | answer | answered | - | yes | lowest plain answer |
| D10 | answerable, correct | 0.714 | answer | answered | - | yes | |
| D28 | answerable, correct | 0.717 | answer | answered | - | yes | |
| D19 | unanswerable | 0.723 | answer | no_answer | sentinel | yes | near-miss |
| D33 | answerable, correct | 0.761 | answer | answered | - | yes | |
| D29 | unanswerable | 0.867 | answer | no_answer | sentinel | yes | near-miss |
| D03 | answerable, correct | 0.900 | answer | answered | - | yes | |
| D26 | answerable, correct | 0.923 | answer | answered | - | yes | |
| D18 | unanswerable | 0.954 | answer | no_answer | sentinel | yes | near-miss |
| D01 | answerable, correct | 0.963 | answer | answered | - | yes | |
| D34 | answerable, correct | 0.979 | answer | answered | - | yes | |
| D08 | answerable, correct | 0.979 | answer | answered | - | yes | |
| D27 | answerable, correct | 0.986 | answer | answered | - | yes | |
| D13 | answerable, correct | 0.989 | answer | answered | - | yes | |
| D11 | answerable, correct | 0.989 | answer | answered | - | yes | |
| D24 | answerable, correct | 0.993 | answer | answered | - | yes | |
| D04 | answerable, correct | 0.993 | answer | answered | - | yes | |
| D21 | answerable, correct | 0.993 | answer | answered | - | yes | |
| D05 | answerable, correct | 0.994 | answer | answered | - | yes | |
| D07 | answerable, failed | 0.995 | answer | no_answer | sentinel | no | page split |
| D14 | answerable, correct | 0.998 | answer | answered | - | yes | |
| D25 | answerable, correct | 0.998 | answer | answered | - | yes | |
| D02 | answerable, failed | 0.999 | answer | no_answer | sentinel | no | borderline sentinel refusal |
| D23 | answerable, correct | 0.999 | answer | answered | - | yes | |
| D17 | answerable, correct | 0.999 | answer | answered | - | yes | |

## Threshold pairs

The band depends only on the top score, and the top scores reproduce exactly between runs. So each pair can be scored from the baseline without a new run, with one limit. Raising `T_REFUSE` only turns items into gate refusals, so its result is exact. Lowering `T_REFUSE` to 0.0152 or below would send D30 to the model, whose answer was not measured. The band is not part of the prompt (`sanad/retrieval/pipeline.py`), and a low-confidence answer scores like a plain one. So `T_CONFIDENT` never changes the score: it only decides which answers carry the amber banner.

| T_REFUSE | T_CONFIDENT | Score | Invented | Gate refusals (of 7 unanswerable) | New false refusals | Amber / plain answers | Source |
|---|---|---|---|---|---|---|---|
| **0.15** | **0.5** | **33/36** | **0** | 4 | 0 | 7 / 20 | measured |
| 0.01 | 0.5 | not measured | not measured | 3 | 0 | | D30 would reach the model |
| 0.02 | 0.5 | 33/36 | 0 | 4 | 0 | 7 / 20 | exact |
| 0.10 | 0.5 | 33/36 | 0 | 4 | 0 | 7 / 20 | exact |
| 0.20 | 0.5 | 33/36 | 0 | 4 | 0 | 7 / 20 | exact |
| 0.25 | 0.5 | 31/36 | 0 | 4 | 2 (D15, D31) | 5 / 20 | exact |
| 0.30 | 0.5 | 30/36 | 0 | 4 | 3 (D15, D31, D09) | 4 / 20 | exact |
| 0.75 | 0.75 | 24/36 | 0 | 5 (adds D19) | 10 (every answer below 0.75: 9 correct, plus D32) | 0 / 17 | exact |
| 0.15 | 0.4 | 33/36 | 0 | 4 | 0 | 4 / 23 | exact |
| 0.15 | 0.6 | 33/36 | 0 | 4 | 0 | 8 / 19 | exact |
| 0.15 | 0.75 | 33/36 | 0 | 4 | 0 | 10 / 17 | exact |
| 0.15 | 0.96 | 33/36 | 0 | 4 | 0 | 13 / 14 | exact |

## Why `T_REFUSE` stays 0.15

- The D4 rule is to refuse as many unanswerable questions as possible at the gate while losing at most one answerable question. The brief is stricter: no new false refusal.
- Any value from just above 0.0152 (D30) up to 0.214 (D15) refuses the same 4 unanswerable questions (D20, D30, D35, D36) and no answerable one. The two rules don't conflict here, because nothing lies between D15 and the first near-miss (D19, 0.723) that one lost item could buy.
- 0.15 is inside that range, round, and toward its upper end, which follows D4's bias toward refusing. Lowering it would weaken the gate with no gain on this data. Raising it to 0.25 costs D15 and D31.
- To refuse a near-miss at the gate, `T_REFUSE` would have to pass 0.723 (D19), which refuses 9 correct answers. **The near-misses D18, D19 and D29 are refused only by the model's `NO_ANSWER`**, in this run and in every earlier one.
- Risk: the margin above the gate is thin. D15 is 0.064 above it and D31 0.085. Both were far lower before recent fixes: D15 was 0.023 before R1b's tashkeel-free query, and D31 was 0.009 before R1c's programme names. A test question phrased in a way the reranker reads badly could land below 0.15. That is a reason to fix retrieval when it happens, not to lower the gate on dev data that shows no such item.

## Why `T_CONFIDENT` stays 0.5

- It is the reranker's even-odds point: below it, the reranker rates its best excerpt as more likely irrelevant than relevant.
- It sits in a gap in the data, between D32 (0.488) and D12 (0.577). Every value in that gap gives the same banding, so it isn't fitted to one item.
- 20 of the 27 answers show the plain band. The 7 amber answers (D15, D31, D09, D06, D22, D16, D32) are all questions whose wording differs from the page: a vocabulary shift, an English question about an Arabic document, or full diacritics. That is what the banner says: "sources that may not fully match your question".
- The amber banner cannot guard the near-misses. Banding all three if the model ever answered one would need `T_CONFIDENT` above 0.954, which puts the banner on 13 of 27 answers, nearly half. A banner on half the answers stops meaning anything.

## The known failing items

- **D02** (0.999) and **D07** (0.995): sentinel refusals in the plain band. No threshold below 0.99 touches them, so neither choice affects them.
- **D32** (0.488): amber at 0.5. At a `T_CONFIDENT` of 0.4877 or less it would show plain, and a `T_REFUSE` above 0.4877 would gate-refuse it. Its failure is the answer language, which R1e is fixing in the prompt. Its score doesn't depend on the prompt, so R1e won't move its band.

## `RERANK_CANDIDATES`: 20 instead of 30, retrieval only

Checked on the 36 dev questions plus the WLP Editor question, as the demo editor, with no model call. Each question was retrieved at both sizes, alternating, twice.

| | 30 (current) | 20 |
|---|---|---|
| recall@10 | 29/29 | **28/29** (D02's expected page drops out of the top 10) |
| top score unchanged | | 36 of 37 (D09 falls from 0.272 to 0.062, below `T_REFUSE`: a new gate refusal) |
| the prompt's 8 excerpts unchanged | | 10 of 37 |
| WLP 84,000 chunk, reranked rank | 5 | 4 |
| rerank stage, median / p90 (74 calls each) | 5.7 s / 6.1 s | 3.8 s / 4.2 s |

Fused candidates 21 to 30 often reach the top 8 after reranking, so cutting them changes most prompts. At 20, recall drops and D09 would be refused, to save 1.9 s of a 33 s answer. **Not changed, and not proposed.**

## When to re-tune

The thresholds depend on the reranker's scores. Re-run this tuning after any change to the reranker, its precision, or the text it scores: the question, the passages, or the expansion of either. R1c's programme names, for example, moved D19 from 0.644 to 0.723 and D31 from 0.009 to 0.235.
