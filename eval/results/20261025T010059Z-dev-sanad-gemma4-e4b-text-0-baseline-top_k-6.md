# Eval: dev set, sanad-gemma4-e4b-text, 0 baseline (top_k 6)

**Score: 27/30**

| | |
|---|---|
| set | dev |
| set_file | eval/dev_questions.yaml |
| set_version | 2 |
| questions | 30 |
| only | - |
| date | 2026-10-25T01:00:59+00:00 |
| git_sha | 9c5c1822ecdd |
| model | sanad-gemma4-e4b-text, 0 baseline (top_k 6) |
| hardware | Apple M5, Docker 16 GB, CPU (containerised Ollama) |
| ollama_version | 0.40.10 |
| server_llm_provider | unknown |
| server_llm_model | unknown |
| signed_in_as | editor (editor@sanad.example) |
| diagnostics_requested | True |
| base_url | http://api:8000 |
| runs | 1 |
| wall_seconds | 1094.5 |

## Totals

- Score: 27/30
- Answerable correct: 22/25
- Refusal accuracy: 5/5 unanswerable refused; false refusals: 2 (D02, D15)
- Invented answers: 0
- recall@5: 25/25; recall@10: 25/25 (an expected page among the candidates)
- Latency, server total: median 28.9 s, p90 64.4 s (n=30)
- Latency, request wall time: median 28.9 s, p90 64.5 s (n=30)
- Failures by category: page_split 1, false_refusal 2
- Stage `embed`: median 0.1 s, p90 0.2 s (n=30)
- Stage `first_token`: median 19.8 s, p90 45.3 s (n=27)
- Stage `generate`: median 22.7 s, p90 66.5 s (n=27)
- Stage `rerank`: median 6.3 s, p90 8.4 s (n=30)
- Stage `retrieve`: median 0.0 s, p90 0.0 s (n=30)
- Run wall time: 18 min 14 s

## Questions

| ID | Lang | Kinds | Outcome | Correct | Category | Cited pages | Expected pages | Rank | Latency |
|---|---|---|---|---|---|---|---|---|---|
| D01 | ar | factual, numeric | answered | yes | - | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p6 | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p6 | 1 | 64.4 s |
| D02 | ar | factual, numeric | no_answer | no | false_refusal | - | yep-final-evaluation-2022.pdf p5 | 2 | 29.5 s |
| D03 | ar | factual, numeric | answered | yes | - | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p4 | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p4 | 1 | 33.2 s |
| D04 | ar | factual, numeric | answered | yes | - | wash-baseline-survey-2017.pdf p4 | wash-baseline-survey-2017.pdf p4, board-minutes-2017-11.txt p2, wash-final-evaluation-2021.pdf p4 | 1 | 36.9 s |
| D05 | ar | factual, numeric | answered | yes | - | chp-household-survey-2021.pdf p4 | chp-household-survey-2021.pdf p4 | 1 | 101.2 s |
| D06 | ar | factual, numeric | low_confidence | yes | - | chp-household-survey-2021.pdf p4 | chp-household-survey-2021.pdf p4 | 1 | 35.1 s |
| D07 | ar | factual, numeric, page_split | no_answer | no | page_split | - | gep-enrolment-survey-2015.pdf p4 | 1 | 75.1 s |
| D08 | en | factual, numeric, english | answered | yes | - | gep-midterm-evaluation-2020.pdf p2 | gep-midterm-evaluation-2020.pdf p2 | 1 | 169.2 s |
| D09 | en | factual, numeric, english, cross_lingual | low_confidence | yes | - | annual-report-2021.pdf p4, annual-report-2021.pdf p14 | annual-report-2021.pdf p4, annual-report-2021.pdf p14 | 3 | 33.0 s |
| D10 | ar | factual, numeric | answered | yes | - | board-minutes-2021-06.docx p2, annual-report-2020.pdf p4, annual-report-2020.pdf p11 | board-minutes-2021-06.docx p2, annual-report-2020.pdf p4, annual-report-2020.pdf p11 | 1 | 31.9 s |
| D11 | ar | factual, numeric | answered | yes | - | board-minutes-2017-11.txt p2 | board-minutes-2017-11.txt p2 | 1 | 29.1 s |
| D12 | ar | factual, numeric | answered | yes | - | annual-report-2021.pdf p6 | annual-report-2021.pdf p6 | 1 | 27.7 s |
| D13 | en | factual, numeric, english, cross_lingual, cross_document | answered | yes | - | gep-enrolment-survey-2015.pdf p2, gep-midterm-evaluation-2020.pdf p3, gep-midterm-evaluation-2020.pdf p4 | gep-enrolment-survey-2015.pdf p2, gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | 3 | 32.2 s |
| D14 | ar | factual, numeric, temporal | answered | yes | - | annual-report-2020.pdf p9, annual-report-2021.pdf p5 | annual-report-2021.pdf p5 | 1 | 26.7 s |
| D15 | ar | factual, diacritics | no_answer | no | false_refusal | - | annual-report-2021.pdf p3, annual-report-2021.pdf p2, gep-enrolment-survey-2015.pdf p1, board-minutes-2021-06.docx p3, annual-report-2016.pdf p2 | 1 | 7.3 s |
| D16 | en | factual, numeric, english, cross_lingual | low_confidence | yes | - | annual-report-2021.pdf p15, annual-report-2021.pdf p3 | annual-report-2021.pdf p3, annual-report-2021.pdf p4, annual-report-2021.pdf p15 | 2 | 26.6 s |
| D17 | ar | factual, numeric, tatweel | answered | yes | - | annual-report-2021.pdf p11 | annual-report-2021.pdf p11, chp-evaluation-2024.pdf p4 | 2 | 26.7 s |
| D18 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 23.6 s |
| D19 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 24.0 s |
| D20 | en | unanswerable, english | no_answer | yes | - | - | - | - | 6.0 s |
| D21 | ar | factual, numeric, version | answered | yes | - | budget-2024-final.pdf p1, annual-report-2023-en.pdf p10, board-minutes-2023-12.pdf p2 | budget-2024-final.pdf p1, budget-2024-final.pdf p2, budget-2024-final.pdf p3, budget-2024-final.pdf p5, board-minutes-2023-12.pdf p2, annual-report-2023-en.pdf p10 | 1 | 32.3 s |
| D22 | ar | factual, temporal | answered | yes | - | annual-report-2022.pdf p2 | annual-report-2022.pdf p2 | 1 | 29.4 s |
| D23 | ar | factual, numeric | answered | yes | - | gep-enrolment-survey-2015.pdf p3 | gep-enrolment-survey-2015.pdf p3 | 2 | 28.7 s |
| D24 | ar | factual, numeric | answered | yes | - | wlp-evaluation-2023.docx p3, wlp-evaluation-2023.docx p4, board-minutes-2023-12.pdf p3, wlp-evaluation-2023.docx p2 | wlp-evaluation-2023.docx p3, wlp-evaluation-2023.docx p4, board-minutes-2023-12.pdf p3 | 1 | 27.5 s |
| D25 | ar | factual, numeric, mixed_content | answered | yes | - | yep-grant-agreement-2021.pdf p3, board-minutes-2021-06.docx p3 | yep-grant-agreement-2021.pdf p3, yep-grant-agreement-2021.pdf p5, board-minutes-2021-06.docx p3 | 1 | 25.4 s |
| D26 | ar | factual, numeric | answered | yes | - | wash-final-evaluation-2021.pdf p2, annual-report-2021.pdf p8, wash-baseline-survey-2017.pdf p5 | wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p5, annual-report-2021.pdf p8 | 1 | 29.6 s |
| D27 | ar | cross_document, temporal, numeric, cross_lingual | answered | yes | - | annual-report-2016.pdf p2, annual-report-2023-en.pdf p3 | annual-report-2016.pdf p2, annual-report-2023-en.pdf p3, annual-report-2023-en.pdf p2 | 1 | 24.4 s |
| D28 | en | factual, numeric, english, cross_lingual | answered | yes | - | wash-final-evaluation-2021.pdf p2, annual-report-2021.pdf p8, wash-final-evaluation-2021.pdf p5 | wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p3, wash-final-evaluation-2021.pdf p5, annual-report-2021.pdf p8, annual-report-2022.pdf p8 | 2 | 27.4 s |
| D29 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 24.6 s |
| D30 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 5.3 s |

Failures:

- **D02** `false_refusal`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.999; best expected page at rank 2 (rerank 0.991, dense rank 3, lexical rank -)
- **D07** `page_split`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.998; best expected page at rank 1 (rerank 0.998, dense rank 1, lexical rank 2)
- **D15** `false_refusal`: outcome no_answer; refusal_reason gate; band refuse; top score 0.023; best expected page at rank 1 (rerank 0.023, dense rank 1, lexical rank 1)

## Category rules

Each failure has one category, the first that applies: `error` (the request failed), `invented_answer` (an unanswerable question was answered, low confidence included), `page_split` (a page-split item failed), `false_refusal` (an answerable question was refused), `retrieval` (no expected page among the candidates), `generation` (an expected page was retrieved, but the facts or the citation are wrong), `unclassified` (retrieval or generation, but the server sent no candidates).
