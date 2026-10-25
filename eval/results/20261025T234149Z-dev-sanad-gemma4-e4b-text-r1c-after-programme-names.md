# Eval: dev set, sanad-gemma4-e4b-text, R1c after (programme names)

**Score: 33/36**

| | |
|---|---|
| set | dev |
| set_file | eval/dev_questions.yaml |
| set_version | 3 |
| questions | 36 |
| only | - |
| date | 2026-10-25T23:41:49+00:00 |
| git_sha | 6aae858a748f |
| model | sanad-gemma4-e4b-text, R1c after (programme names) |
| hardware | Apple M5, Docker 16 GB fresh VM, CPU (containerised Ollama), no other stacks |
| ollama_version | 0.40.10 |
| server_llm_provider | unknown |
| server_llm_model | unknown |
| signed_in_as | editor (editor@sanad.example) |
| diagnostics_requested | True |
| base_url | http://api:8000 |
| runs | 1 |
| wall_seconds | 558.7 |

## Totals

- Score: 33/36
- Answerable correct: 26/29
- Refusal accuracy: 7/7 unanswerable refused; false refusals: 1 (D02)
- Invented answers: 0
- recall@5: 29/29; recall@10: 29/29 (an expected page among the candidates)
- Latency, server total: median 9.4 s, p90 40.1 s (n=36)
- Latency, request wall time: median 9.4 s, p90 40.1 s (n=36)
- Failures by category: page_split 1, false_refusal 1, generation 1
- Stage `embed`: median 0.0 s, p90 0.1 s (n=36)
- Stage `first_token`: median 0.3 s, p90 25.9 s (n=32)
- Stage `generate`: median 3.9 s, p90 34.0 s (n=32)
- Stage `rerank`: median 5.7 s, p90 6.4 s (n=36)
- Stage `retrieve`: median 0.0 s, p90 0.0 s (n=36)
- Run wall time: 9 min 19 s

## Questions

| ID | Lang | Kinds | Outcome | Correct | Category | Cited pages | Expected pages | Rank | Latency |
|---|---|---|---|---|---|---|---|---|---|
| D01 | ar | factual, numeric | answered | yes | - | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p5, yep-final-evaluation-2022.pdf p6 | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p6 | 1 | 9.3 s |
| D02 | ar | factual, numeric | no_answer | no | false_refusal | - | yep-final-evaluation-2022.pdf p5 | 2 | 6.1 s |
| D03 | ar | factual, numeric | answered | yes | - | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p4 | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p4 | 1 | 8.5 s |
| D04 | ar | factual, numeric | answered | yes | - | wash-baseline-survey-2017.pdf p4 | wash-baseline-survey-2017.pdf p4, board-minutes-2017-11.txt p2, wash-final-evaluation-2021.pdf p4 | 1 | 9.7 s |
| D05 | ar | factual, numeric | answered | yes | - | chp-household-survey-2021.pdf p4 | chp-household-survey-2021.pdf p4 | 1 | 8.6 s |
| D06 | ar | factual, numeric | low_confidence | yes | - | chp-household-survey-2021.pdf p4 | chp-household-survey-2021.pdf p4 | 1 | 9.9 s |
| D07 | ar | factual, numeric, page_split | no_answer | no | page_split | - | gep-enrolment-survey-2015.pdf p4 | 1 | 6.9 s |
| D08 | en | factual, numeric, english | answered | yes | - | gep-midterm-evaluation-2020.pdf p2 | gep-midterm-evaluation-2020.pdf p2 | 1 | 8.1 s |
| D09 | en | factual, numeric, english, cross_lingual | low_confidence | yes | - | annual-report-2021.pdf p4, annual-report-2021.pdf p14 | annual-report-2021.pdf p4, annual-report-2021.pdf p14 | 3 | 7.8 s |
| D10 | ar | factual, numeric | answered | yes | - | board-minutes-2021-06.docx p2, annual-report-2020.pdf p4, annual-report-2020.pdf p11 | board-minutes-2021-06.docx p2, annual-report-2020.pdf p4, annual-report-2020.pdf p11 | 1 | 10.3 s |
| D11 | ar | factual, numeric | answered | yes | - | board-minutes-2017-11.txt p2 | board-minutes-2017-11.txt p2 | 1 | 9.9 s |
| D12 | ar | factual, numeric | answered | yes | - | annual-report-2021.pdf p6 | annual-report-2021.pdf p6 | 1 | 8.1 s |
| D13 | en | factual, numeric, english, cross_lingual, cross_document | answered | yes | - | gep-enrolment-survey-2015.pdf p2, gep-midterm-evaluation-2020.pdf p2 | gep-enrolment-survey-2015.pdf p2, gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | 3 | 12.0 s |
| D14 | ar | factual, numeric, temporal | answered | yes | - | annual-report-2020.pdf p9, annual-report-2021.pdf p5 | annual-report-2021.pdf p5 | 1 | 39.3 s |
| D15 | ar | factual, diacritics | low_confidence | yes | - | annual-report-2016.pdf p2, annual-report-2021.pdf p3 | annual-report-2021.pdf p3, annual-report-2021.pdf p2, gep-enrolment-survey-2015.pdf p1, board-minutes-2021-06.docx p3, annual-report-2016.pdf p2 | 1 | 7.9 s |
| D16 | en | factual, numeric, english, cross_lingual | low_confidence | yes | - | annual-report-2021.pdf p15, annual-report-2021.pdf p3 | annual-report-2021.pdf p3, annual-report-2021.pdf p4, annual-report-2021.pdf p15 | 2 | 8.8 s |
| D17 | ar | factual, numeric, tatweel | answered | yes | - | annual-report-2021.pdf p11 | annual-report-2021.pdf p11, chp-evaluation-2024.pdf p4 | 2 | 9.4 s |
| D18 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 34.1 s |
| D19 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 34.2 s |
| D20 | en | unanswerable, english | no_answer | yes | - | - | - | - | 5.6 s |
| D21 | ar | factual, numeric, version | answered | yes | - | budget-2024-final.pdf p1, annual-report-2023-en.pdf p10, budget-2024-final.pdf p2, board-minutes-2023-12.pdf p2 | budget-2024-final.pdf p1, budget-2024-final.pdf p2, budget-2024-final.pdf p3, budget-2024-final.pdf p5, board-minutes-2023-12.pdf p2, annual-report-2023-en.pdf p10 | 1 | 10.9 s |
| D22 | ar | factual, temporal | low_confidence | yes | - | annual-report-2022.pdf p2 | annual-report-2022.pdf p2 | 1 | 11.2 s |
| D23 | ar | factual, numeric | answered | yes | - | gep-enrolment-survey-2015.pdf p3 | gep-enrolment-survey-2015.pdf p3 | 2 | 9.2 s |
| D24 | ar | factual, numeric | answered | yes | - | wlp-evaluation-2023.docx p3, wlp-evaluation-2023.docx p4, board-minutes-2023-12.pdf p3 | wlp-evaluation-2023.docx p3, wlp-evaluation-2023.docx p4, board-minutes-2023-12.pdf p3 | 1 | 41.0 s |
| D25 | ar | factual, numeric, mixed_content | answered | yes | - | yep-grant-agreement-2021.pdf p3, board-minutes-2021-06.docx p3 | yep-grant-agreement-2021.pdf p3, yep-grant-agreement-2021.pdf p5, board-minutes-2021-06.docx p3 | 1 | 10.0 s |
| D26 | ar | factual, numeric | answered | yes | - | wash-final-evaluation-2021.pdf p2, annual-report-2021.pdf p8, annual-report-2020.pdf p7 | wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p5, annual-report-2021.pdf p8 | 1 | 10.3 s |
| D27 | ar | cross_document, temporal, numeric, cross_lingual | answered | yes | - | annual-report-2016.pdf p2, annual-report-2023-en.pdf p3 | annual-report-2016.pdf p2, annual-report-2023-en.pdf p3, annual-report-2023-en.pdf p2 | 1 | 8.5 s |
| D28 | en | factual, numeric, english, cross_lingual | answered | yes | - | wash-final-evaluation-2021.pdf p2, annual-report-2021.pdf p8 | wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p3, wash-final-evaluation-2021.pdf p5, annual-report-2021.pdf p8, annual-report-2022.pdf p8 | 2 | 8.5 s |
| D29 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 6.5 s |
| D30 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 5.0 s |
| D31 | ar | overview, colloquial, cross_document | low_confidence | yes | - | annual-report-2016.pdf p4, annual-report-2020.pdf p9, annual-report-2022.pdf p11, chp-evaluation-2024.pdf p2, chp-evaluation-2024.pdf p4 | chp-household-survey-2021.pdf p1, chp-household-survey-2021.pdf p2, chp-household-survey-2021.pdf p3, chp-household-survey-2021.pdf p4, chp-household-survey-2021.pdf p5, chp-evaluation-2024.pdf p1, chp-evaluation-2024.pdf p2, chp-evaluation-2024.pdf p3, chp-evaluation-2024.pdf p4, chp-evaluation-2024.pdf p5, chp-evaluation-2024.pdf p6, annual-report-2016.pdf p4, annual-report-2016.pdf p5, annual-report-2020.pdf p2, annual-report-2020.pdf p3, annual-report-2020.pdf p4, annual-report-2020.pdf p5, annual-report-2020.pdf p9, annual-report-2020.pdf p11, annual-report-2021.pdf p5, annual-report-2021.pdf p11, annual-report-2021.pdf p14, annual-report-2021.pdf p16, annual-report-2022.pdf p3, annual-report-2022.pdf p4, annual-report-2022.pdf p5, annual-report-2022.pdf p11, annual-report-2022.pdf p13, annual-report-2023-en.pdf p3, annual-report-2023-en.pdf p4, annual-report-2023-en.pdf p7, annual-report-2023-en.pdf p9, annual-report-2023-en.pdf p10 | 1 | 53.6 s |
| D32 | en | overview, colloquial, cross_document, cross_lingual | low_confidence | no | generation | annual-report-2016.pdf p4, annual-report-2020.pdf p9, annual-report-2021.pdf p5, chp-evaluation-2024.pdf p4, chp-evaluation-2024.pdf p2 | chp-household-survey-2021.pdf p1, chp-household-survey-2021.pdf p2, chp-household-survey-2021.pdf p3, chp-household-survey-2021.pdf p4, chp-household-survey-2021.pdf p5, chp-evaluation-2024.pdf p1, chp-evaluation-2024.pdf p2, chp-evaluation-2024.pdf p3, chp-evaluation-2024.pdf p4, chp-evaluation-2024.pdf p5, chp-evaluation-2024.pdf p6, annual-report-2016.pdf p4, annual-report-2016.pdf p5, annual-report-2020.pdf p2, annual-report-2020.pdf p3, annual-report-2020.pdf p4, annual-report-2020.pdf p5, annual-report-2020.pdf p9, annual-report-2020.pdf p11, annual-report-2021.pdf p5, annual-report-2021.pdf p11, annual-report-2021.pdf p14, annual-report-2021.pdf p16, annual-report-2022.pdf p3, annual-report-2022.pdf p4, annual-report-2022.pdf p5, annual-report-2022.pdf p11, annual-report-2022.pdf p13, annual-report-2023-en.pdf p3, annual-report-2023-en.pdf p4, annual-report-2023-en.pdf p7, annual-report-2023-en.pdf p9, annual-report-2023-en.pdf p10 | 1 | 38.7 s |
| D33 | ar | overview, colloquial, cross_document | answered | yes | - | annual-report-2021.pdf p8, annual-report-2020.pdf p7, wash-final-evaluation-2021.pdf p2 | wash-baseline-survey-2017.pdf p1, wash-baseline-survey-2017.pdf p2, wash-baseline-survey-2017.pdf p3, wash-baseline-survey-2017.pdf p4, wash-baseline-survey-2017.pdf p5, wash-donor-agreement-2018.pdf p1, wash-donor-agreement-2018.pdf p2, wash-donor-agreement-2018.pdf p3, wash-donor-agreement-2018.pdf p4, wash-donor-agreement-2018.pdf p5, wash-donor-agreement-2018.pdf p6, wash-final-evaluation-2021.pdf p1, wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p3, wash-final-evaluation-2021.pdf p4, wash-final-evaluation-2021.pdf p5, wash-final-evaluation-2021.pdf p6, wash-final-evaluation-2021.pdf p7, annual-report-2020.pdf p5, annual-report-2020.pdf p7, annual-report-2020.pdf p11, annual-report-2021.pdf p5, annual-report-2021.pdf p8, annual-report-2021.pdf p14, annual-report-2022.pdf p5, annual-report-2022.pdf p8, annual-report-2022.pdf p13, annual-report-2023-en.pdf p2, annual-report-2023-en.pdf p4, annual-report-2023-en.pdf p9 | 1 | 40.1 s |
| D34 | en | overview, english, cross_document | answered | yes | - | gep-midterm-evaluation-2020.pdf p6, gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | gep-enrolment-survey-2015.pdf p1, gep-enrolment-survey-2015.pdf p2, gep-enrolment-survey-2015.pdf p3, gep-enrolment-survey-2015.pdf p4, gep-donor-agreement-2019.pdf p1, gep-donor-agreement-2019.pdf p2, gep-donor-agreement-2019.pdf p3, gep-donor-agreement-2019.pdf p4, gep-donor-agreement-2019.pdf p5, gep-donor-agreement-2019.pdf p6, gep-midterm-evaluation-2020.pdf p1, gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p3, gep-midterm-evaluation-2020.pdf p4, gep-midterm-evaluation-2020.pdf p5, gep-midterm-evaluation-2020.pdf p6, annual-report-2016.pdf p3, annual-report-2016.pdf p5, annual-report-2016.pdf p6, annual-report-2020.pdf p5, annual-report-2020.pdf p8, annual-report-2020.pdf p11, annual-report-2021.pdf p5, annual-report-2021.pdf p14, annual-report-2022.pdf p5, annual-report-2022.pdf p9, annual-report-2022.pdf p13, annual-report-2023-en.pdf p4, annual-report-2023-en.pdf p9 | 1 | 40.2 s |
| D35 | ar | unanswerable, overview, colloquial | no_answer | yes | - | - | - | - | 5.0 s |
| D36 | en | unanswerable, overview | no_answer | yes | - | - | - | - | 5.4 s |

Failures:

- **D02** `false_refusal`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.999; best expected page at rank 2 (rerank 0.992, dense rank 4, lexical rank -)
- **D07** `page_split`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.995; best expected page at rank 1 (rerank 0.995, dense rank 1, lexical rank 2)
- **D32** `generation`: outcome low_confidence; band low_confidence; top score 0.488; missing facts health; citation ok; best expected page at rank 1 (rerank 0.488, dense rank 3, lexical rank 8)

## Category rules

Each failure has one category, the first that applies: `error` (the request failed), `invented_answer` (an unanswerable question was answered, low confidence included), `page_split` (a page-split item failed), `false_refusal` (an answerable question was refused), `retrieval` (no expected page among the candidates), `generation` (an expected page was retrieved, but the facts or the citation are wrong), `unclassified` (retrieval or generation, but the server sent no candidates).
