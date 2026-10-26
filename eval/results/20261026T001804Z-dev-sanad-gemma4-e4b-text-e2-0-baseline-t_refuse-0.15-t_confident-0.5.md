# Eval: dev set, sanad-gemma4-e4b-text, E2 0 baseline T_REFUSE 0.15 T_CONFIDENT 0.5

**Score: 33/36**

| | |
|---|---|
| set | dev |
| set_file | eval/dev_questions.yaml |
| set_version | 3 |
| questions | 36 |
| only | - |
| date | 2026-10-26T00:18:04+00:00 |
| git_sha | 2016a25696d3 |
| model | sanad-gemma4-e4b-text, E2 0 baseline T_REFUSE 0.15 T_CONFIDENT 0.5 |
| hardware | Apple M5, Docker 16 GB, CPU (containerised Ollama), no other stack running |
| ollama_version | 0.40.10 |
| server_llm_provider | unknown |
| server_llm_model | unknown |
| signed_in_as | editor (editor@sanad.example) |
| diagnostics_requested | True |
| base_url | http://api:8000 |
| runs | 1 |
| wall_seconds | 1067.4 |

## Totals

- Score: 33/36
- Answerable correct: 26/29
- Refusal accuracy: 7/7 unanswerable refused; false refusals: 1 (D02)
- Invented answers: 0
- recall@5: 29/29; recall@10: 29/29 (an expected page among the candidates)
- Latency, server total: median 32.6 s, p90 38.9 s (n=36)
- Latency, request wall time: median 32.6 s, p90 38.9 s (n=36)
- Failures by category: page_split 1, false_refusal 1, generation 1
- Stage `embed`: median 0.1 s, p90 0.1 s (n=36)
- Stage `first_token`: median 24.9 s, p90 27.9 s (n=32)
- Stage `generate`: median 27.0 s, p90 32.9 s (n=32)
- Stage `rerank`: median 5.8 s, p90 6.2 s (n=36)
- Stage `retrieve`: median 0.0 s, p90 0.0 s (n=36)
- Run wall time: 17 min 47 s

## Questions

| ID | Lang | Kinds | Outcome | Correct | Category | Cited pages | Expected pages | Rank | Latency |
|---|---|---|---|---|---|---|---|---|---|
| D01 | ar | factual, numeric | answered | yes | - | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p5, yep-final-evaluation-2022.pdf p6 | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p6 | 1 | 34.0 s |
| D02 | ar | factual, numeric | no_answer | no | false_refusal | - | yep-final-evaluation-2022.pdf p5 | 2 | 32.5 s |
| D03 | ar | factual, numeric | answered | yes | - | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p4 | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p4 | 1 | 44.5 s |
| D04 | ar | factual, numeric | answered | yes | - | wash-baseline-survey-2017.pdf p4 | wash-baseline-survey-2017.pdf p4, board-minutes-2017-11.txt p2, wash-final-evaluation-2021.pdf p4 | 1 | 34.0 s |
| D05 | ar | factual, numeric | answered | yes | - | chp-household-survey-2021.pdf p4 | chp-household-survey-2021.pdf p4 | 1 | 7.6 s |
| D06 | ar | factual, numeric | low_confidence | yes | - | chp-household-survey-2021.pdf p4 | chp-household-survey-2021.pdf p4 | 1 | 33.6 s |
| D07 | ar | factual, numeric, page_split | no_answer | no | page_split | - | gep-enrolment-survey-2015.pdf p4 | 1 | 33.1 s |
| D08 | en | factual, numeric, english | answered | yes | - | gep-midterm-evaluation-2020.pdf p2 | gep-midterm-evaluation-2020.pdf p2 | 1 | 33.4 s |
| D09 | en | factual, numeric, english, cross_lingual | low_confidence | yes | - | annual-report-2021.pdf p4, annual-report-2021.pdf p14 | annual-report-2021.pdf p4, annual-report-2021.pdf p14 | 3 | 28.3 s |
| D10 | ar | factual, numeric | answered | yes | - | board-minutes-2021-06.docx p2, annual-report-2020.pdf p4, annual-report-2020.pdf p11 | board-minutes-2021-06.docx p2, annual-report-2020.pdf p4, annual-report-2020.pdf p11 | 1 | 33.5 s |
| D11 | ar | factual, numeric | answered | yes | - | board-minutes-2017-11.txt p2 | board-minutes-2017-11.txt p2 | 1 | 31.1 s |
| D12 | ar | factual, numeric | answered | yes | - | annual-report-2021.pdf p6 | annual-report-2021.pdf p6 | 1 | 32.8 s |
| D13 | en | factual, numeric, english, cross_lingual, cross_document | answered | yes | - | gep-enrolment-survey-2015.pdf p2, gep-midterm-evaluation-2020.pdf p2 | gep-enrolment-survey-2015.pdf p2, gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | 3 | 37.7 s |
| D14 | ar | factual, numeric, temporal, cross_document | answered | yes | - | annual-report-2020.pdf p9, annual-report-2021.pdf p5 | annual-report-2021.pdf p5, annual-report-2020.pdf p5, annual-report-2020.pdf p9, annual-report-2021.pdf p11, annual-report-2022.pdf p5, chp-evaluation-2024.pdf p4 | 1 | 32.7 s |
| D15 | ar | factual, diacritics | low_confidence | yes | - | annual-report-2016.pdf p2, annual-report-2021.pdf p3 | annual-report-2021.pdf p3, annual-report-2021.pdf p2, gep-enrolment-survey-2015.pdf p1, board-minutes-2021-06.docx p3, annual-report-2016.pdf p2 | 1 | 30.1 s |
| D16 | en | factual, numeric, english, cross_lingual | low_confidence | yes | - | annual-report-2021.pdf p15 | annual-report-2021.pdf p3, annual-report-2021.pdf p4, annual-report-2021.pdf p15 | 2 | 28.5 s |
| D17 | ar | factual, numeric, tatweel | answered | yes | - | annual-report-2021.pdf p11 | annual-report-2021.pdf p11, chp-evaluation-2024.pdf p4 | 2 | 30.6 s |
| D18 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 31.6 s |
| D19 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 30.0 s |
| D20 | en | unanswerable, english | no_answer | yes | - | - | - | - | 5.7 s |
| D21 | ar | factual, numeric, version | answered | yes | - | budget-2024-final.pdf p1, annual-report-2023-en.pdf p10, budget-2024-final.pdf p2, board-minutes-2023-12.pdf p2 | budget-2024-final.pdf p1, budget-2024-final.pdf p2, budget-2024-final.pdf p3, budget-2024-final.pdf p5, board-minutes-2023-12.pdf p2, annual-report-2023-en.pdf p10 | 1 | 31.9 s |
| D22 | ar | factual, temporal | low_confidence | yes | - | annual-report-2022.pdf p2 | annual-report-2022.pdf p2 | 1 | 36.9 s |
| D23 | ar | factual, numeric | answered | yes | - | gep-enrolment-survey-2015.pdf p3 | gep-enrolment-survey-2015.pdf p3 | 2 | 34.1 s |
| D24 | ar | factual, numeric | answered | yes | - | wlp-evaluation-2023.docx p3, wlp-evaluation-2023.docx p4, board-minutes-2023-12.pdf p3 | wlp-evaluation-2023.docx p3, wlp-evaluation-2023.docx p4, board-minutes-2023-12.pdf p3 | 1 | 35.6 s |
| D25 | ar | factual, numeric, mixed_content | answered | yes | - | yep-grant-agreement-2021.pdf p3, board-minutes-2021-06.docx p3 | yep-grant-agreement-2021.pdf p3, yep-grant-agreement-2021.pdf p5, board-minutes-2021-06.docx p3 | 1 | 31.4 s |
| D26 | ar | factual, numeric | answered | yes | - | wash-final-evaluation-2021.pdf p2, annual-report-2021.pdf p8, annual-report-2020.pdf p7 | wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p5, annual-report-2021.pdf p8 | 1 | 37.4 s |
| D27 | ar | cross_document, temporal, numeric, cross_lingual | answered | yes | - | annual-report-2016.pdf p2, annual-report-2023-en.pdf p3 | annual-report-2016.pdf p2, annual-report-2023-en.pdf p3, annual-report-2023-en.pdf p2 | 1 | 26.6 s |
| D28 | en | factual, numeric, english, cross_lingual | answered | yes | - | wash-final-evaluation-2021.pdf p2, annual-report-2021.pdf p8 | wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p3, wash-final-evaluation-2021.pdf p5, annual-report-2021.pdf p8, annual-report-2022.pdf p8 | 2 | 31.0 s |
| D29 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 28.6 s |
| D30 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 5.0 s |
| D31 | ar | overview, colloquial, cross_document | low_confidence | yes | - | annual-report-2016.pdf p4, annual-report-2020.pdf p9, annual-report-2022.pdf p11, chp-evaluation-2024.pdf p2, chp-evaluation-2024.pdf p4 | chp-household-survey-2021.pdf p1, chp-household-survey-2021.pdf p2, chp-household-survey-2021.pdf p3, chp-household-survey-2021.pdf p4, chp-household-survey-2021.pdf p5, chp-evaluation-2024.pdf p1, chp-evaluation-2024.pdf p2, chp-evaluation-2024.pdf p3, chp-evaluation-2024.pdf p4, chp-evaluation-2024.pdf p5, chp-evaluation-2024.pdf p6, annual-report-2016.pdf p4, annual-report-2016.pdf p5, annual-report-2020.pdf p2, annual-report-2020.pdf p3, annual-report-2020.pdf p4, annual-report-2020.pdf p5, annual-report-2020.pdf p9, annual-report-2020.pdf p11, annual-report-2021.pdf p5, annual-report-2021.pdf p11, annual-report-2021.pdf p14, annual-report-2021.pdf p16, annual-report-2022.pdf p3, annual-report-2022.pdf p4, annual-report-2022.pdf p5, annual-report-2022.pdf p11, annual-report-2022.pdf p13, annual-report-2023-en.pdf p3, annual-report-2023-en.pdf p4, annual-report-2023-en.pdf p7, annual-report-2023-en.pdf p9, annual-report-2023-en.pdf p10 | 1 | 38.9 s |
| D32 | en | overview, colloquial, cross_document, cross_lingual | low_confidence | no | generation | annual-report-2016.pdf p4, annual-report-2020.pdf p9, annual-report-2021.pdf p5, chp-evaluation-2024.pdf p4, chp-evaluation-2024.pdf p2 | chp-household-survey-2021.pdf p1, chp-household-survey-2021.pdf p2, chp-household-survey-2021.pdf p3, chp-household-survey-2021.pdf p4, chp-household-survey-2021.pdf p5, chp-evaluation-2024.pdf p1, chp-evaluation-2024.pdf p2, chp-evaluation-2024.pdf p3, chp-evaluation-2024.pdf p4, chp-evaluation-2024.pdf p5, chp-evaluation-2024.pdf p6, annual-report-2016.pdf p4, annual-report-2016.pdf p5, annual-report-2020.pdf p2, annual-report-2020.pdf p3, annual-report-2020.pdf p4, annual-report-2020.pdf p5, annual-report-2020.pdf p9, annual-report-2020.pdf p11, annual-report-2021.pdf p5, annual-report-2021.pdf p11, annual-report-2021.pdf p14, annual-report-2021.pdf p16, annual-report-2022.pdf p3, annual-report-2022.pdf p4, annual-report-2022.pdf p5, annual-report-2022.pdf p11, annual-report-2022.pdf p13, annual-report-2023-en.pdf p3, annual-report-2023-en.pdf p4, annual-report-2023-en.pdf p7, annual-report-2023-en.pdf p9, annual-report-2023-en.pdf p10 | 1 | 35.6 s |
| D33 | ar | overview, colloquial, cross_document | answered | yes | - | annual-report-2021.pdf p8, annual-report-2020.pdf p7, wash-final-evaluation-2021.pdf p2 | wash-baseline-survey-2017.pdf p1, wash-baseline-survey-2017.pdf p2, wash-baseline-survey-2017.pdf p3, wash-baseline-survey-2017.pdf p4, wash-baseline-survey-2017.pdf p5, wash-donor-agreement-2018.pdf p1, wash-donor-agreement-2018.pdf p2, wash-donor-agreement-2018.pdf p3, wash-donor-agreement-2018.pdf p4, wash-donor-agreement-2018.pdf p5, wash-donor-agreement-2018.pdf p6, wash-final-evaluation-2021.pdf p1, wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p3, wash-final-evaluation-2021.pdf p4, wash-final-evaluation-2021.pdf p5, wash-final-evaluation-2021.pdf p6, wash-final-evaluation-2021.pdf p7, annual-report-2020.pdf p5, annual-report-2020.pdf p7, annual-report-2020.pdf p11, annual-report-2021.pdf p5, annual-report-2021.pdf p8, annual-report-2021.pdf p14, annual-report-2022.pdf p5, annual-report-2022.pdf p8, annual-report-2022.pdf p13, annual-report-2023-en.pdf p2, annual-report-2023-en.pdf p4, annual-report-2023-en.pdf p9 | 1 | 39.4 s |
| D34 | en | overview, english, cross_document | answered | yes | - | gep-midterm-evaluation-2020.pdf p6, gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | gep-enrolment-survey-2015.pdf p1, gep-enrolment-survey-2015.pdf p2, gep-enrolment-survey-2015.pdf p3, gep-enrolment-survey-2015.pdf p4, gep-donor-agreement-2019.pdf p1, gep-donor-agreement-2019.pdf p2, gep-donor-agreement-2019.pdf p3, gep-donor-agreement-2019.pdf p4, gep-donor-agreement-2019.pdf p5, gep-donor-agreement-2019.pdf p6, gep-midterm-evaluation-2020.pdf p1, gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p3, gep-midterm-evaluation-2020.pdf p4, gep-midterm-evaluation-2020.pdf p5, gep-midterm-evaluation-2020.pdf p6, annual-report-2016.pdf p3, annual-report-2016.pdf p5, annual-report-2016.pdf p6, annual-report-2020.pdf p5, annual-report-2020.pdf p8, annual-report-2020.pdf p11, annual-report-2021.pdf p5, annual-report-2021.pdf p14, annual-report-2022.pdf p5, annual-report-2022.pdf p9, annual-report-2022.pdf p13, annual-report-2023-en.pdf p4, annual-report-2023-en.pdf p9 | 1 | 39.1 s |
| D35 | ar | unanswerable, overview, colloquial | no_answer | yes | - | - | - | - | 4.9 s |
| D36 | en | unanswerable, overview | no_answer | yes | - | - | - | - | 5.5 s |

Failures:

- **D02** `false_refusal`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.999; best expected page at rank 2 (rerank 0.992, dense rank 4, lexical rank -)
- **D07** `page_split`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.995; best expected page at rank 1 (rerank 0.995, dense rank 1, lexical rank 2)
- **D32** `generation`: outcome low_confidence; band low_confidence; top score 0.488; missing facts health; citation ok; best expected page at rank 1 (rerank 0.488, dense rank 3, lexical rank 12)

## Category rules

Each failure has one category, the first that applies: `error` (the request failed), `invented_answer` (an unanswerable question was answered, low confidence included), `page_split` (a page-split item failed), `false_refusal` (an answerable question was refused), `retrieval` (no expected page among the candidates), `generation` (an expected page was retrieved, but the facts or the citation are wrong), `unclassified` (retrieval or generation, but the server sent no candidates).
