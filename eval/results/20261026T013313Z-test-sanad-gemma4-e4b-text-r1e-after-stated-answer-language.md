# Eval: test set, sanad-gemma4-e4b-text, R1e after (stated answer language)

**Score: 11/15**

> **INVENTED ANSWERS: 1 (T23).** The system answered a question the documents can't answer. This is the failure the refusal gate exists to prevent.

| | |
|---|---|
| set | test |
| set_file | eval/questions.yaml |
| set_version | 2 |
| questions | 15 |
| only | - |
| date | 2026-10-26T01:33:13+00:00 |
| git_sha | ce8f88b6922d |
| model | sanad-gemma4-e4b-text, R1e after (stated answer language) |
| hardware | Apple M5, Docker 16 GB fresh VM, CPU (containerised Ollama), no other stacks |
| ollama_version | 0.40.10 |
| server_llm_provider | unknown |
| server_llm_model | unknown |
| signed_in_as | editor (editor@sanad.example) |
| diagnostics_requested | True |
| base_url | http://api:8000 |
| runs | 1 |
| wall_seconds | 437.8 |

## Totals

- Score: 11/15
- Answerable correct: 9/12
- Refusal accuracy: 2/3 unanswerable refused; false refusals: 0
- Invented answers: 1 (T23)
- recall@5: 12/12; recall@10: 12/12 (an expected page among the candidates)
- Latency, server total: median 31.4 s, p90 33.7 s (n=15)
- Latency, request wall time: median 31.4 s, p90 33.7 s (n=15)
- Failures by category: invented_answer 1, page_split 1, generation 2
- Stage `embed`: median 0.0 s, p90 0.1 s (n=15)
- Stage `first_token`: median 23.4 s, p90 24.5 s (n=14)
- Stage `generate`: median 26.1 s, p90 27.1 s (n=14)
- Stage `rerank`: median 6.0 s, p90 6.8 s (n=15)
- Stage `retrieve`: median 0.0 s, p90 0.0 s (n=15)
- Run wall time: 7 min 18 s

## Questions

| ID | Lang | Kinds | Outcome | Correct | Category | Cited pages | Expected pages | Rank | Latency |
|---|---|---|---|---|---|---|---|---|---|
| T01 | ar | factual, numeric | answered | yes | - | annual-report-2021.pdf p6 | annual-report-2021.pdf p6, annual-report-2021.pdf p7, yep-final-evaluation-2022.pdf p4 | 1 | 32.1 s |
| T04 | ar | factual, numeric | answered | yes | - | chp-household-survey-2021.pdf p3, annual-report-2021.pdf p11 | chp-household-survey-2021.pdf p3, annual-report-2021.pdf p11, chp-evaluation-2024.pdf p5 | 1 | 32.9 s |
| T07 | ar | factual, numeric, mixed_content | answered | yes | - | spc-donor-agreement-2023.docx p2, board-minutes-2023-03.pdf p3 | spc-donor-agreement-2023.docx p2, spc-donor-agreement-2023.docx p3, board-minutes-2023-03.pdf p3, annual-report-2023-en.pdf p8 | 1 | 32.1 s |
| T09 | ar | factual, numeric, tatweel | answered | yes | - | annual-report-2021.pdf p9 | annual-report-2021.pdf p9 | 1 | 33.0 s |
| T10 | ar | factual, numeric, diacritics | answered | yes | - | annual-report-2021.pdf p3, annual-report-2021.pdf p4 | annual-report-2021.pdf p3, annual-report-2021.pdf p4 | 1 | 29.6 s |
| T12 | ar | factual, numeric | low_confidence | no | generation | budget-2018.docx p3 | budget-2018.docx p3 | 1 | 27.4 s |
| T13 | ar | factual, numeric | answered | no | generation | yep-tracer-survey-2023.pdf p3 | yep-tracer-survey-2023.pdf p3, annual-report-2023-en.pdf p5 | 1 | 27.9 s |
| T14 | ar | factual, numeric, page_split | no_answer | no | page_split | - | chp-evaluation-2024.pdf p5 | 3 | 27.9 s |
| T15 | ar | cross_document, temporal, numeric | answered | yes | - | annual-report-2021.pdf p8, wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p4 | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p4, annual-report-2021.pdf p8 | 1 | 33.0 s |
| T16 | ar | cross_document, temporal, numeric | answered | yes | - | yep-final-evaluation-2022.pdf p4, annual-report-2022.pdf p6 | annual-report-2020.pdf p6, annual-report-2022.pdf p6, yep-final-evaluation-2022.pdf p4 | 1 | 31.4 s |
| T18 | en | factual, numeric, english | answered | yes | - | gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | 1 | 33.7 s |
| T19 | en | factual, numeric, english, cross_lingual | answered | yes | - | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p5, yep-tracer-survey-2023.pdf p4 | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p5 | 1 | 30.4 s |
| T21 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 26.1 s |
| T23 | en | unanswerable, near_miss, english | answered | no | invented_answer | gep-donor-agreement-2019.pdf p3, annual-report-2022.pdf p9 | - | - | 33.9 s |
| T24 | ar | unanswerable | no_answer | yes | - | - | - | - | 6.1 s |

Failures:

- **T12** `generation`: outcome low_confidence; band low_confidence; top score 0.255; missing facts 140,000; citation ok; best expected page at rank 1 (rerank 0.255, dense rank 1, lexical rank -)
- **T13** `generation`: outcome answered; band answer; top score 0.999; missing facts 64; citation ok; best expected page at rank 1 (rerank 0.999, dense rank 2, lexical rank -)
- **T14** `page_split`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.997; best expected page at rank 3 (rerank 0.872, dense rank 5, lexical rank 18)
- **T23** `invented_answer`: outcome answered; band answer; top score 0.998

## Category rules

Each failure has one category, the first that applies: `error` (the request failed), `invented_answer` (an unanswerable question was answered, low confidence included), `page_split` (a page-split item failed), `false_refusal` (an answerable question was refused), `retrieval` (no expected page among the candidates), `generation` (an expected page was retrieved, but the facts or the citation are wrong), `unclassified` (retrieval or generation, but the server sent no candidates).
