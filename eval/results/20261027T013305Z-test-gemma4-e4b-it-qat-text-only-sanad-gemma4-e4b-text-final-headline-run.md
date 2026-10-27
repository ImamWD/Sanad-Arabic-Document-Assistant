# Eval: test set, gemma4:e4b-it-qat text-only (sanad-gemma4-e4b-text), final headline run

**Score: 11.0/15 (range 11-11 over 3 runs)**

> **INVENTED ANSWERS: 1 (T23).** The system answered a question the documents can't answer. This is the failure the refusal gate exists to prevent.

| | |
|---|---|
| set | test |
| set_file | eval/questions.yaml |
| set_version | 2 |
| questions | 15 |
| only | - |
| date | 2026-10-27T01:33:05+00:00 |
| git_sha | 80eac662df49 |
| model | gemma4:e4b-it-qat text-only (sanad-gemma4-e4b-text), final headline run |
| hardware | Apple M5 (10 cores), 24 GB RAM, Docker Desktop VM 16 GB, CPU only (containerised Ollama), freshly restarted, no other stack |
| ollama_version | 0.40.10 |
| server_llm_provider | unknown |
| server_llm_model | unknown |
| signed_in_as | editor (editor@sanad.example) |
| diagnostics_requested | True |
| base_url | http://api:8000 |
| runs | 3 |
| wall_seconds | 749.4 |

## Totals

- Scores over 3 runs: 11, 11, 11
- Run 1: Score: 11/15
- Run 1: Answerable correct: 9/12
- Run 1: Refusal accuracy: 2/3 unanswerable refused; false refusals: 0
- Run 1: Invented answers: 1 (T23)
- Run 1: recall@5: 12/12; recall@10: 12/12 (an expected page among the candidates)
- Run 1: Latency, server total: median 34.9 s, p90 43.5 s (n=15)
- Run 1: Latency, request wall time: median 34.9 s, p90 43.5 s (n=15)
- Run 1: Failures by category: invented_answer 1, page_split 1, generation 2
- Run 1: Stage `embed`: median 0.1 s, p90 0.1 s (n=15)
- Run 1: Stage `first_token`: median 25.9 s, p90 31.2 s (n=14)
- Run 1: Stage `generate`: median 28.6 s, p90 37.3 s (n=14)
- Run 1: Stage `rerank`: median 6.1 s, p90 6.8 s (n=15)
- Run 1: Stage `retrieve`: median 0.0 s, p90 0.0 s (n=15)
- Run 2: Score: 11/15
- Run 2: Answerable correct: 9/12
- Run 2: Refusal accuracy: 2/3 unanswerable refused; false refusals: 0
- Run 2: Invented answers: 1 (T23)
- Run 2: recall@5: 12/12; recall@10: 12/12 (an expected page among the candidates)
- Run 2: Latency, server total: median 8.6 s, p90 10.2 s (n=15)
- Run 2: Latency, request wall time: median 8.6 s, p90 10.2 s (n=15)
- Run 2: Failures by category: invented_answer 1, page_split 1, generation 2
- Run 2: Stage `embed`: median 0.1 s, p90 0.1 s (n=15)
- Run 2: Stage `first_token`: median 0.2 s, p90 0.5 s (n=14)
- Run 2: Stage `generate`: median 2.7 s, p90 4.1 s (n=14)
- Run 2: Stage `rerank`: median 5.8 s, p90 6.5 s (n=15)
- Run 2: Stage `retrieve`: median 0.0 s, p90 0.0 s (n=15)
- Run 3: Score: 11/15
- Run 3: Answerable correct: 9/12
- Run 3: Refusal accuracy: 2/3 unanswerable refused; false refusals: 0
- Run 3: Invented answers: 1 (T23)
- Run 3: recall@5: 12/12; recall@10: 12/12 (an expected page among the candidates)
- Run 3: Latency, server total: median 8.5 s, p90 9.6 s (n=15)
- Run 3: Latency, request wall time: median 8.5 s, p90 9.6 s (n=15)
- Run 3: Failures by category: invented_answer 1, page_split 1, generation 2
- Run 3: Stage `embed`: median 0.0 s, p90 0.1 s (n=15)
- Run 3: Stage `first_token`: median 0.2 s, p90 0.4 s (n=14)
- Run 3: Stage `generate`: median 2.8 s, p90 3.5 s (n=14)
- Run 3: Stage `rerank`: median 5.9 s, p90 6.4 s (n=15)
- Run 3: Stage `retrieve`: median 0.0 s, p90 0.0 s (n=15)
- Run wall time: 12 min 29 s

## Questions, run 1

| ID | Lang | Kinds | Outcome | Correct | Category | Cited pages | Expected pages | Rank | Latency |
|---|---|---|---|---|---|---|---|---|---|
| T01 | ar | factual, numeric | answered | yes | - | annual-report-2021.pdf p6 | annual-report-2021.pdf p6, annual-report-2021.pdf p7, yep-final-evaluation-2022.pdf p4 | 1 | 34.9 s |
| T04 | ar | factual, numeric | answered | yes | - | chp-household-survey-2021.pdf p3, annual-report-2021.pdf p11 | chp-household-survey-2021.pdf p3, annual-report-2021.pdf p11, chp-evaluation-2024.pdf p5 | 1 | 37.1 s |
| T07 | ar | factual, numeric, mixed_content | answered | yes | - | spc-donor-agreement-2023.docx p2, board-minutes-2023-03.pdf p3 | spc-donor-agreement-2023.docx p2, spc-donor-agreement-2023.docx p3, board-minutes-2023-03.pdf p3, annual-report-2023-en.pdf p8 | 1 | 47.1 s |
| T09 | ar | factual, numeric, tatweel | answered | yes | - | annual-report-2021.pdf p9 | annual-report-2021.pdf p9 | 1 | 43.5 s |
| T10 | ar | factual, numeric, diacritics | answered | yes | - | annual-report-2021.pdf p3, annual-report-2021.pdf p4 | annual-report-2021.pdf p3, annual-report-2021.pdf p4 | 1 | 33.1 s |
| T12 | ar | factual, numeric | low_confidence | no | generation | budget-2018.docx p3 | budget-2018.docx p3 | 1 | 34.0 s |
| T13 | ar | factual, numeric | answered | no | generation | yep-tracer-survey-2023.pdf p3 | yep-tracer-survey-2023.pdf p3, annual-report-2023-en.pdf p5 | 1 | 30.8 s |
| T14 | ar | factual, numeric, page_split | no_answer | no | page_split | - | chp-evaluation-2024.pdf p5 | 3 | 30.4 s |
| T15 | ar | cross_document, temporal, numeric | answered | yes | - | annual-report-2021.pdf p8, wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p4 | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p4, annual-report-2021.pdf p8 | 1 | 35.3 s |
| T16 | ar | cross_document, temporal, numeric | answered | yes | - | yep-final-evaluation-2022.pdf p4, annual-report-2022.pdf p6 | annual-report-2020.pdf p6, annual-report-2022.pdf p6, yep-final-evaluation-2022.pdf p4 | 1 | 33.4 s |
| T18 | en | factual, numeric, english | answered | yes | - | gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | 1 | 36.4 s |
| T19 | en | factual, numeric, english, cross_lingual | answered | yes | - | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p5, yep-tracer-survey-2023.pdf p4 | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p5 | 1 | 34.9 s |
| T21 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 29.7 s |
| T23 | en | unanswerable, near_miss, english | answered | no | invented_answer | gep-donor-agreement-2019.pdf p3, annual-report-2022.pdf p9 | - | - | 35.7 s |
| T24 | ar | unanswerable | no_answer | yes | - | - | - | - | 6.0 s |

Failures:

- **T12** `generation`: outcome low_confidence; band low_confidence; top score 0.255; missing facts 140,000; citation ok; best expected page at rank 1 (rerank 0.255, dense rank 1, lexical rank -)
- **T13** `generation`: outcome answered; band answer; top score 0.999; missing facts 64; citation ok; best expected page at rank 1 (rerank 0.999, dense rank 2, lexical rank -)
- **T14** `page_split`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.997; best expected page at rank 3 (rerank 0.872, dense rank 5, lexical rank 19)
- **T23** `invented_answer`: outcome answered; band answer; top score 0.998

## Questions, run 2

| ID | Lang | Kinds | Outcome | Correct | Category | Cited pages | Expected pages | Rank | Latency |
|---|---|---|---|---|---|---|---|---|---|
| T01 | ar | factual, numeric | answered | yes | - | annual-report-2021.pdf p6 | annual-report-2021.pdf p6, annual-report-2021.pdf p7, yep-final-evaluation-2022.pdf p4 | 1 | 7.9 s |
| T04 | ar | factual, numeric | answered | yes | - | chp-household-survey-2021.pdf p3, annual-report-2021.pdf p11 | chp-household-survey-2021.pdf p3, annual-report-2021.pdf p11, chp-evaluation-2024.pdf p5 | 1 | 9.9 s |
| T07 | ar | factual, numeric, mixed_content | answered | yes | - | spc-donor-agreement-2023.docx p2, board-minutes-2023-03.pdf p3 | spc-donor-agreement-2023.docx p2, spc-donor-agreement-2023.docx p3, board-minutes-2023-03.pdf p3, annual-report-2023-en.pdf p8 | 1 | 8.9 s |
| T09 | ar | factual, numeric, tatweel | answered | yes | - | annual-report-2021.pdf p9 | annual-report-2021.pdf p9 | 1 | 10.2 s |
| T10 | ar | factual, numeric, diacritics | answered | yes | - | annual-report-2021.pdf p3, annual-report-2021.pdf p4 | annual-report-2021.pdf p3, annual-report-2021.pdf p4 | 1 | 7.4 s |
| T12 | ar | factual, numeric | low_confidence | no | generation | budget-2018.docx p3 | budget-2018.docx p3 | 1 | 9.5 s |
| T13 | ar | factual, numeric | answered | no | generation | yep-tracer-survey-2023.pdf p3 | yep-tracer-survey-2023.pdf p3, annual-report-2023-en.pdf p5 | 1 | 7.6 s |
| T14 | ar | factual, numeric, page_split | no_answer | no | page_split | - | chp-evaluation-2024.pdf p5 | 3 | 6.6 s |
| T15 | ar | cross_document, temporal, numeric | answered | yes | - | annual-report-2021.pdf p8, wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p4 | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p4, annual-report-2021.pdf p8 | 1 | 10.3 s |
| T16 | ar | cross_document, temporal, numeric | answered | yes | - | yep-final-evaluation-2022.pdf p4, annual-report-2022.pdf p6 | annual-report-2020.pdf p6, annual-report-2022.pdf p6, yep-final-evaluation-2022.pdf p4 | 1 | 8.5 s |
| T18 | en | factual, numeric, english | answered | yes | - | gep-midterm-evaluation-2020.pdf p2 | gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | 1 | 8.6 s |
| T19 | en | factual, numeric, english, cross_lingual | answered | yes | - | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p5, yep-tracer-survey-2023.pdf p4 | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p5 | 1 | 8.6 s |
| T21 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 5.7 s |
| T23 | en | unanswerable, near_miss, english | answered | no | invented_answer | gep-donor-agreement-2019.pdf p3, annual-report-2022.pdf p9 | - | - | 9.8 s |
| T24 | ar | unanswerable | no_answer | yes | - | - | - | - | 5.7 s |

Failures:

- **T12** `generation`: outcome low_confidence; band low_confidence; top score 0.255; missing facts 140,000; citation ok; best expected page at rank 1 (rerank 0.255, dense rank 1, lexical rank -)
- **T13** `generation`: outcome answered; band answer; top score 0.999; missing facts 64; citation ok; best expected page at rank 1 (rerank 0.999, dense rank 2, lexical rank -)
- **T14** `page_split`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.997; best expected page at rank 3 (rerank 0.872, dense rank 5, lexical rank 19)
- **T23** `invented_answer`: outcome answered; band answer; top score 0.998

## Questions, run 3

| ID | Lang | Kinds | Outcome | Correct | Category | Cited pages | Expected pages | Rank | Latency |
|---|---|---|---|---|---|---|---|---|---|
| T01 | ar | factual, numeric | answered | yes | - | annual-report-2021.pdf p6 | annual-report-2021.pdf p6, annual-report-2021.pdf p7, yep-final-evaluation-2022.pdf p4 | 1 | 8.2 s |
| T04 | ar | factual, numeric | answered | yes | - | chp-household-survey-2021.pdf p3, annual-report-2021.pdf p11 | chp-household-survey-2021.pdf p3, annual-report-2021.pdf p11, chp-evaluation-2024.pdf p5 | 1 | 9.6 s |
| T07 | ar | factual, numeric, mixed_content | answered | yes | - | spc-donor-agreement-2023.docx p2, board-minutes-2023-03.pdf p3 | spc-donor-agreement-2023.docx p2, spc-donor-agreement-2023.docx p3, board-minutes-2023-03.pdf p3, annual-report-2023-en.pdf p8 | 1 | 8.8 s |
| T09 | ar | factual, numeric, tatweel | answered | yes | - | annual-report-2021.pdf p9 | annual-report-2021.pdf p9 | 1 | 9.7 s |
| T10 | ar | factual, numeric, diacritics | answered | yes | - | annual-report-2021.pdf p3, annual-report-2021.pdf p4 | annual-report-2021.pdf p3, annual-report-2021.pdf p4 | 1 | 7.3 s |
| T12 | ar | factual, numeric | low_confidence | no | generation | budget-2018.docx p3 | budget-2018.docx p3 | 1 | 9.0 s |
| T13 | ar | factual, numeric | answered | no | generation | yep-tracer-survey-2023.pdf p3 | yep-tracer-survey-2023.pdf p3, annual-report-2023-en.pdf p5 | 1 | 6.6 s |
| T14 | ar | factual, numeric, page_split | no_answer | no | page_split | - | chp-evaluation-2024.pdf p5 | 3 | 6.3 s |
| T15 | ar | cross_document, temporal, numeric | answered | yes | - | annual-report-2021.pdf p8, wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p4 | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p4, annual-report-2021.pdf p8 | 1 | 8.9 s |
| T16 | ar | cross_document, temporal, numeric | answered | yes | - | yep-final-evaluation-2022.pdf p4, annual-report-2022.pdf p6 | annual-report-2020.pdf p6, annual-report-2022.pdf p6, yep-final-evaluation-2022.pdf p4 | 1 | 8.5 s |
| T18 | en | factual, numeric, english | answered | yes | - | gep-midterm-evaluation-2020.pdf p2 | gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | 1 | 9.2 s |
| T19 | en | factual, numeric, english, cross_lingual | answered | yes | - | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p5, yep-tracer-survey-2023.pdf p4 | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p5 | 1 | 8.5 s |
| T21 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 5.7 s |
| T23 | en | unanswerable, near_miss, english | answered | no | invented_answer | gep-donor-agreement-2019.pdf p3, annual-report-2022.pdf p9 | - | - | 9.6 s |
| T24 | ar | unanswerable | no_answer | yes | - | - | - | - | 5.8 s |

Failures:

- **T12** `generation`: outcome low_confidence; band low_confidence; top score 0.255; missing facts 140,000; citation ok; best expected page at rank 1 (rerank 0.255, dense rank 1, lexical rank -)
- **T13** `generation`: outcome answered; band answer; top score 0.999; missing facts 64; citation ok; best expected page at rank 1 (rerank 0.999, dense rank 2, lexical rank -)
- **T14** `page_split`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.997; best expected page at rank 3 (rerank 0.872, dense rank 5, lexical rank 19)
- **T23** `invented_answer`: outcome answered; band answer; top score 0.998

## Correct in how many runs

| ID | Correct |
|---|---|
| T01 | 3/3 |
| T04 | 3/3 |
| T07 | 3/3 |
| T09 | 3/3 |
| T10 | 3/3 |
| T12 | 0/3 |
| T13 | 0/3 |
| T14 | 0/3 |
| T15 | 3/3 |
| T16 | 3/3 |
| T18 | 3/3 |
| T19 | 3/3 |
| T21 | 3/3 |
| T23 | 0/3 |
| T24 | 3/3 |

## Category rules

Each failure has one category, the first that applies: `error` (the request failed), `invented_answer` (an unanswerable question was answered, low confidence included), `page_split` (a page-split item failed), `false_refusal` (an answerable question was refused), `retrieval` (no expected page among the candidates), `generation` (an expected page was retrieved, but the facts or the citation are wrong), `unclassified` (retrieval or generation, but the server sent no candidates).
