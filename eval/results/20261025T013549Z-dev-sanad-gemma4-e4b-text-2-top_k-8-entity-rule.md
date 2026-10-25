# Eval: dev set, sanad-gemma4-e4b-text, 2 top_k 8 + entity rule

**Score: 27/30**

| | |
|---|---|
| set | dev |
| set_file | eval/dev_questions.yaml |
| set_version | 2 |
| questions | 30 |
| only | - |
| date | 2026-10-25T01:35:49+00:00 |
| git_sha | 7afaedbd54fd |
| model | sanad-gemma4-e4b-text, 2 top_k 8 + entity rule |
| hardware | Apple M5, Docker 16 GB, CPU (containerised Ollama) |
| ollama_version | 0.40.10 |
| server_llm_provider | unknown |
| server_llm_model | unknown |
| signed_in_as | editor (editor@sanad.example) |
| diagnostics_requested | True |
| base_url | http://api:8000 |
| runs | 1 |
| wall_seconds | 934.7 |

## Totals

- Score: 27/30
- Answerable correct: 22/25
- Refusal accuracy: 5/5 unanswerable refused; false refusals: 1 (D15)
- Invented answers: 0
- recall@5: 25/25; recall@10: 25/25 (an expected page among the candidates)
- Latency, server total: median 33.2 s, p90 38.5 s (n=30)
- Latency, request wall time: median 33.2 s, p90 38.5 s (n=30)
- Failures by category: page_split 1, false_refusal 1, generation 1
- Stage `embed`: median 0.1 s, p90 0.1 s (n=30)
- Stage `first_token`: median 25.9 s, p90 28.7 s (n=27)
- Stage `generate`: median 27.2 s, p90 32.2 s (n=27)
- Stage `rerank`: median 6.1 s, p90 6.8 s (n=30)
- Stage `retrieve`: median 0.0 s, p90 0.0 s (n=30)
- Run wall time: 15 min 35 s

## Questions

| ID | Lang | Kinds | Outcome | Correct | Category | Cited pages | Expected pages | Rank | Latency |
|---|---|---|---|---|---|---|---|---|---|
| D01 | ar | factual, numeric | answered | yes | - | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p6 | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p6 | 1 | 34.8 s |
| D02 | ar | factual, numeric | answered | yes | - | yep-final-evaluation-2022.pdf p5 | yep-final-evaluation-2022.pdf p5 | 2 | 35.1 s |
| D03 | ar | factual, numeric | answered | yes | - | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p4 | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p4 | 1 | 34.7 s |
| D04 | ar | factual, numeric | answered | yes | - | wash-baseline-survey-2017.pdf p4 | wash-baseline-survey-2017.pdf p4, board-minutes-2017-11.txt p2, wash-final-evaluation-2021.pdf p4 | 1 | 32.8 s |
| D05 | ar | factual, numeric | answered | yes | - | chp-household-survey-2021.pdf p4 | chp-household-survey-2021.pdf p4 | 1 | 31.7 s |
| D06 | ar | factual, numeric | low_confidence | yes | - | chp-household-survey-2021.pdf p4 | chp-household-survey-2021.pdf p4 | 1 | 32.9 s |
| D07 | ar | factual, numeric, page_split | no_answer | no | page_split | - | gep-enrolment-survey-2015.pdf p4 | 1 | 33.1 s |
| D08 | en | factual, numeric, english | answered | yes | - | gep-midterm-evaluation-2020.pdf p2 | gep-midterm-evaluation-2020.pdf p2 | 1 | 33.7 s |
| D09 | en | factual, numeric, english, cross_lingual | low_confidence | yes | - | annual-report-2021.pdf p4, annual-report-2021.pdf p14 | annual-report-2021.pdf p4, annual-report-2021.pdf p14 | 3 | 28.6 s |
| D10 | ar | factual, numeric | answered | yes | - | board-minutes-2021-06.docx p2, annual-report-2020.pdf p4, annual-report-2020.pdf p11 | board-minutes-2021-06.docx p2, annual-report-2020.pdf p4, annual-report-2020.pdf p11 | 1 | 34.1 s |
| D11 | ar | factual, numeric | answered | yes | - | board-minutes-2017-11.txt p2 | board-minutes-2017-11.txt p2 | 1 | 31.8 s |
| D12 | ar | factual, numeric | answered | yes | - | annual-report-2021.pdf p6 | annual-report-2021.pdf p6 | 1 | 31.7 s |
| D13 | en | factual, numeric, english, cross_lingual, cross_document | answered | yes | - | gep-enrolment-survey-2015.pdf p2, gep-midterm-evaluation-2020.pdf p2 | gep-enrolment-survey-2015.pdf p2, gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | 3 | 39.3 s |
| D14 | ar | factual, numeric, temporal | answered | no | generation | annual-report-2020.pdf p9, annual-report-2021.pdf p11 | annual-report-2021.pdf p5 | 1 | 32.9 s |
| D15 | ar | factual, diacritics | no_answer | no | false_refusal | - | annual-report-2021.pdf p3, annual-report-2021.pdf p2, gep-enrolment-survey-2015.pdf p1, board-minutes-2021-06.docx p3, annual-report-2016.pdf p2 | 1 | 7.3 s |
| D16 | en | factual, numeric, english, cross_lingual | low_confidence | yes | - | annual-report-2021.pdf p15, annual-report-2021.pdf p3 | annual-report-2021.pdf p3, annual-report-2021.pdf p4, annual-report-2021.pdf p15 | 2 | 29.8 s |
| D17 | ar | factual, numeric, tatweel | answered | yes | - | annual-report-2021.pdf p11, chp-evaluation-2024.pdf p4 | annual-report-2021.pdf p11, chp-evaluation-2024.pdf p4 | 2 | 34.2 s |
| D18 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 29.0 s |
| D19 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 35.9 s |
| D20 | en | unanswerable, english | no_answer | yes | - | - | - | - | 5.9 s |
| D21 | ar | factual, numeric, version | answered | yes | - | budget-2024-final.pdf p1, budget-2024-final.pdf p2, annual-report-2023-en.pdf p10, board-minutes-2023-12.pdf p2 | budget-2024-final.pdf p1, budget-2024-final.pdf p2, budget-2024-final.pdf p3, budget-2024-final.pdf p5, board-minutes-2023-12.pdf p2, annual-report-2023-en.pdf p10 | 1 | 36.8 s |
| D22 | ar | factual, temporal | answered | yes | - | annual-report-2022.pdf p2 | annual-report-2022.pdf p2 | 1 | 38.6 s |
| D23 | ar | factual, numeric | answered | yes | - | gep-enrolment-survey-2015.pdf p3 | gep-enrolment-survey-2015.pdf p3 | 2 | 37.9 s |
| D24 | ar | factual, numeric | answered | yes | - | wlp-evaluation-2023.docx p3, wlp-evaluation-2023.docx p4, board-minutes-2023-12.pdf p3 | wlp-evaluation-2023.docx p3, wlp-evaluation-2023.docx p4, board-minutes-2023-12.pdf p3 | 1 | 38.5 s |
| D25 | ar | factual, numeric, mixed_content | answered | yes | - | yep-grant-agreement-2021.pdf p3, board-minutes-2021-06.docx p3 | yep-grant-agreement-2021.pdf p3, yep-grant-agreement-2021.pdf p5, board-minutes-2021-06.docx p3 | 1 | 32.5 s |
| D26 | ar | factual, numeric | answered | yes | - | wash-final-evaluation-2021.pdf p2, annual-report-2021.pdf p8, annual-report-2020.pdf p7 | wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p5, annual-report-2021.pdf p8 | 1 | 38.5 s |
| D27 | ar | cross_document, temporal, numeric, cross_lingual | answered | yes | - | annual-report-2016.pdf p2, annual-report-2023-en.pdf p3 | annual-report-2016.pdf p2, annual-report-2023-en.pdf p3, annual-report-2023-en.pdf p2 | 1 | 29.6 s |
| D28 | en | factual, numeric, english, cross_lingual | answered | yes | - | wash-final-evaluation-2021.pdf p2, annual-report-2021.pdf p8 | wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p3, wash-final-evaluation-2021.pdf p5, annual-report-2021.pdf p8, annual-report-2022.pdf p8 | 2 | 34.1 s |
| D29 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 33.3 s |
| D30 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 5.3 s |

Failures:

- **D07** `page_split`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.998; best expected page at rank 1 (rerank 0.998, dense rank 1, lexical rank 2)
- **D14** `generation`: outcome answered; band answer; top score 0.988; no expected page cited; best expected page at rank 1 (rerank 0.988, dense rank 1, lexical rank 1)
- **D15** `false_refusal`: outcome no_answer; refusal_reason gate; band refuse; top score 0.023; best expected page at rank 1 (rerank 0.023, dense rank 1, lexical rank 1)

## Category rules

Each failure has one category, the first that applies: `error` (the request failed), `invented_answer` (an unanswerable question was answered, low confidence included), `page_split` (a page-split item failed), `false_refusal` (an answerable question was refused), `retrieval` (no expected page among the candidates), `generation` (an expected page was retrieved, but the facts or the citation are wrong), `unclassified` (retrieval or generation, but the server sent no candidates).
