# Eval: dev set, sanad-gemma4-e4b-text, R1f after (rule 7 near-miss)

**Score: 36/39**

> **INVENTED ANSWERS: 1 (D37).** The system answered a question the documents can't answer. This is the failure the refusal gate exists to prevent.

| | |
|---|---|
| set | dev |
| set_file | eval/dev_questions.yaml |
| set_version | 4 |
| questions | 39 |
| only | - |
| date | 2026-10-27T00:35:26+00:00 |
| git_sha | 6f46cac24d72 |
| model | sanad-gemma4-e4b-text, R1f after (rule 7 near-miss) |
| hardware | Apple M5, Docker 16 GB fresh VM, CPU (containerised Ollama), no other stacks, generation about 10 tok/s |
| ollama_version | 0.40.10 |
| server_llm_provider | unknown |
| server_llm_model | unknown |
| signed_in_as | editor (editor@sanad.example) |
| diagnostics_requested | True |
| base_url | http://api:8000 |
| runs | 1 |
| wall_seconds | 1822.6 |

## Totals

- Score: 36/39
- Answerable correct: 27/29
- Refusal accuracy: 9/10 unanswerable refused; false refusals: 1 (D02)
- Invented answers: 1 (D37)
- recall@5: 29/29; recall@10: 29/29 (an expected page among the candidates)
- Latency, server total: median 38.5 s, p90 65.5 s (n=39)
- Latency, request wall time: median 38.5 s, p90 65.6 s (n=39)
- Failures by category: invented_answer 1, page_split 1, false_refusal 1
- Stage `embed`: median 0.1 s, p90 0.1 s (n=39)
- Stage `first_token`: median 27.9 s, p90 45.0 s (n=35)
- Stage `generate`: median 33.4 s, p90 55.3 s (n=35)
- Stage `rerank`: median 6.2 s, p90 7.9 s (n=39)
- Stage `retrieve`: median 0.0 s, p90 0.0 s (n=39)
- Run wall time: 30 min 23 s

## Questions

| ID | Lang | Kinds | Outcome | Correct | Category | Cited pages | Expected pages | Rank | Latency |
|---|---|---|---|---|---|---|---|---|---|
| D01 | ar | factual, numeric | answered | yes | - | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p5, yep-final-evaluation-2022.pdf p6 | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p6 | 1 | 47.6 s |
| D02 | ar | factual, numeric | no_answer | no | false_refusal | - | yep-final-evaluation-2022.pdf p5 | 2 | 44.8 s |
| D03 | ar | factual, numeric | answered | yes | - | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p4 | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p4 | 1 | 219.3 s |
| D04 | ar | factual, numeric | answered | yes | - | wash-baseline-survey-2017.pdf p4 | wash-baseline-survey-2017.pdf p4, board-minutes-2017-11.txt p2, wash-final-evaluation-2021.pdf p4 | 1 | 199.1 s |
| D05 | ar | factual, numeric | answered | yes | - | chp-household-survey-2021.pdf p4 | chp-household-survey-2021.pdf p4 | 1 | 65.5 s |
| D06 | ar | factual, numeric | low_confidence | yes | - | chp-household-survey-2021.pdf p4 | chp-household-survey-2021.pdf p4 | 1 | 117.5 s |
| D07 | ar | factual, numeric, page_split | no_answer | no | page_split | - | gep-enrolment-survey-2015.pdf p4 | 1 | 51.9 s |
| D08 | en | factual, numeric, english | answered | yes | - | gep-midterm-evaluation-2020.pdf p2 | gep-midterm-evaluation-2020.pdf p2 | 1 | 46.8 s |
| D09 | en | factual, numeric, english, cross_lingual | low_confidence | yes | - | annual-report-2021.pdf p4, annual-report-2021.pdf p14 | annual-report-2021.pdf p4, annual-report-2021.pdf p14 | 3 | 44.2 s |
| D10 | ar | factual, numeric | answered | yes | - | board-minutes-2021-06.docx p2, annual-report-2020.pdf p4, annual-report-2020.pdf p11 | board-minutes-2021-06.docx p2, annual-report-2020.pdf p4, annual-report-2020.pdf p11 | 1 | 35.8 s |
| D11 | ar | factual, numeric | answered | yes | - | board-minutes-2017-11.txt p2 | board-minutes-2017-11.txt p2 | 1 | 38.9 s |
| D12 | ar | factual, numeric | answered | yes | - | annual-report-2021.pdf p6 | annual-report-2021.pdf p6 | 1 | 34.8 s |
| D13 | en | factual, numeric, english, cross_lingual, cross_document | answered | yes | - | gep-enrolment-survey-2015.pdf p2, gep-midterm-evaluation-2020.pdf p3, gep-midterm-evaluation-2020.pdf p2 | gep-enrolment-survey-2015.pdf p2, gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | 3 | 38.5 s |
| D14 | ar | factual, numeric, temporal, cross_document | answered | yes | - | annual-report-2021.pdf p5, annual-report-2020.pdf p9 | annual-report-2021.pdf p5, annual-report-2020.pdf p5, annual-report-2020.pdf p9, annual-report-2021.pdf p11, annual-report-2022.pdf p5, chp-evaluation-2024.pdf p4 | 1 | 31.9 s |
| D15 | ar | factual, diacritics | low_confidence | yes | - | annual-report-2016.pdf p2, annual-report-2021.pdf p3, gep-enrolment-survey-2015.pdf p1 | annual-report-2021.pdf p3, annual-report-2021.pdf p2, gep-enrolment-survey-2015.pdf p1, board-minutes-2021-06.docx p3, annual-report-2016.pdf p2 | 1 | 37.3 s |
| D16 | en | factual, numeric, english, cross_lingual | low_confidence | yes | - | annual-report-2021.pdf p15, annual-report-2021.pdf p3 | annual-report-2021.pdf p3, annual-report-2021.pdf p4, annual-report-2021.pdf p15 | 2 | 38.0 s |
| D17 | ar | factual, numeric, tatweel | answered | yes | - | annual-report-2021.pdf p11 | annual-report-2021.pdf p11, chp-evaluation-2024.pdf p4 | 2 | 36.7 s |
| D18 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 36.1 s |
| D19 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 37.0 s |
| D20 | en | unanswerable, english | no_answer | yes | - | - | - | - | 6.1 s |
| D21 | ar | factual, numeric, version | answered | yes | - | budget-2024-final.pdf p1, annual-report-2023-en.pdf p10, budget-2024-final.pdf p2, board-minutes-2023-12.pdf p2 | budget-2024-final.pdf p1, budget-2024-final.pdf p2, budget-2024-final.pdf p3, budget-2024-final.pdf p5, board-minutes-2023-12.pdf p2, annual-report-2023-en.pdf p10 | 1 | 41.0 s |
| D22 | ar | factual, temporal | low_confidence | yes | - | annual-report-2022.pdf p2 | annual-report-2022.pdf p2 | 1 | 44.9 s |
| D23 | ar | factual, numeric | answered | yes | - | gep-enrolment-survey-2015.pdf p3 | gep-enrolment-survey-2015.pdf p3 | 2 | 40.3 s |
| D24 | ar | factual, numeric | answered | yes | - | wlp-evaluation-2023.docx p3, wlp-evaluation-2023.docx p4, board-minutes-2023-12.pdf p3 | wlp-evaluation-2023.docx p3, wlp-evaluation-2023.docx p4, board-minutes-2023-12.pdf p3 | 1 | 41.3 s |
| D25 | ar | factual, numeric, mixed_content | answered | yes | - | yep-grant-agreement-2021.pdf p3, board-minutes-2021-06.docx p3 | yep-grant-agreement-2021.pdf p3, yep-grant-agreement-2021.pdf p5, board-minutes-2021-06.docx p3 | 1 | 37.9 s |
| D26 | ar | factual, numeric | answered | yes | - | wash-final-evaluation-2021.pdf p2, annual-report-2021.pdf p8, wash-baseline-survey-2017.pdf p5 | wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p5, annual-report-2021.pdf p8 | 1 | 40.1 s |
| D27 | ar | cross_document, temporal, numeric, cross_lingual | answered | yes | - | annual-report-2016.pdf p2, annual-report-2023-en.pdf p3 | annual-report-2016.pdf p2, annual-report-2023-en.pdf p3, annual-report-2023-en.pdf p2 | 1 | 31.4 s |
| D28 | en | factual, numeric, english, cross_lingual | answered | yes | - | wash-final-evaluation-2021.pdf p2, annual-report-2021.pdf p8 | wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p3, wash-final-evaluation-2021.pdf p5, annual-report-2021.pdf p8, annual-report-2022.pdf p8 | 2 | 33.6 s |
| D29 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 30.8 s |
| D30 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 5.0 s |
| D31 | ar | overview, colloquial, cross_document | low_confidence | yes | - | annual-report-2016.pdf p4, annual-report-2020.pdf p9, annual-report-2022.pdf p11 | chp-household-survey-2021.pdf p1, chp-household-survey-2021.pdf p2, chp-household-survey-2021.pdf p3, chp-household-survey-2021.pdf p4, chp-household-survey-2021.pdf p5, chp-evaluation-2024.pdf p1, chp-evaluation-2024.pdf p2, chp-evaluation-2024.pdf p3, chp-evaluation-2024.pdf p4, chp-evaluation-2024.pdf p5, chp-evaluation-2024.pdf p6, annual-report-2016.pdf p4, annual-report-2016.pdf p5, annual-report-2020.pdf p2, annual-report-2020.pdf p3, annual-report-2020.pdf p4, annual-report-2020.pdf p5, annual-report-2020.pdf p9, annual-report-2020.pdf p11, annual-report-2021.pdf p5, annual-report-2021.pdf p11, annual-report-2021.pdf p14, annual-report-2021.pdf p16, annual-report-2022.pdf p3, annual-report-2022.pdf p4, annual-report-2022.pdf p5, annual-report-2022.pdf p11, annual-report-2022.pdf p13, annual-report-2023-en.pdf p3, annual-report-2023-en.pdf p4, annual-report-2023-en.pdf p7, annual-report-2023-en.pdf p9, annual-report-2023-en.pdf p10 | 1 | 41.2 s |
| D32 | en | overview, colloquial, cross_document, cross_lingual | low_confidence | yes | - | annual-report-2016.pdf p4, annual-report-2020.pdf p9, annual-report-2021.pdf p5, chp-evaluation-2024.pdf p4, chp-evaluation-2024.pdf p2 | chp-household-survey-2021.pdf p1, chp-household-survey-2021.pdf p2, chp-household-survey-2021.pdf p3, chp-household-survey-2021.pdf p4, chp-household-survey-2021.pdf p5, chp-evaluation-2024.pdf p1, chp-evaluation-2024.pdf p2, chp-evaluation-2024.pdf p3, chp-evaluation-2024.pdf p4, chp-evaluation-2024.pdf p5, chp-evaluation-2024.pdf p6, annual-report-2016.pdf p4, annual-report-2016.pdf p5, annual-report-2020.pdf p2, annual-report-2020.pdf p3, annual-report-2020.pdf p4, annual-report-2020.pdf p5, annual-report-2020.pdf p9, annual-report-2020.pdf p11, annual-report-2021.pdf p5, annual-report-2021.pdf p11, annual-report-2021.pdf p14, annual-report-2021.pdf p16, annual-report-2022.pdf p3, annual-report-2022.pdf p4, annual-report-2022.pdf p5, annual-report-2022.pdf p11, annual-report-2022.pdf p13, annual-report-2023-en.pdf p3, annual-report-2023-en.pdf p4, annual-report-2023-en.pdf p7, annual-report-2023-en.pdf p9, annual-report-2023-en.pdf p10 | 1 | 39.1 s |
| D33 | ar | overview, colloquial, cross_document | answered | yes | - | annual-report-2021.pdf p8, wash-final-evaluation-2021.pdf p2 | wash-baseline-survey-2017.pdf p1, wash-baseline-survey-2017.pdf p2, wash-baseline-survey-2017.pdf p3, wash-baseline-survey-2017.pdf p4, wash-baseline-survey-2017.pdf p5, wash-donor-agreement-2018.pdf p1, wash-donor-agreement-2018.pdf p2, wash-donor-agreement-2018.pdf p3, wash-donor-agreement-2018.pdf p4, wash-donor-agreement-2018.pdf p5, wash-donor-agreement-2018.pdf p6, wash-final-evaluation-2021.pdf p1, wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p3, wash-final-evaluation-2021.pdf p4, wash-final-evaluation-2021.pdf p5, wash-final-evaluation-2021.pdf p6, wash-final-evaluation-2021.pdf p7, annual-report-2020.pdf p5, annual-report-2020.pdf p7, annual-report-2020.pdf p11, annual-report-2021.pdf p5, annual-report-2021.pdf p8, annual-report-2021.pdf p14, annual-report-2022.pdf p5, annual-report-2022.pdf p8, annual-report-2022.pdf p13, annual-report-2023-en.pdf p2, annual-report-2023-en.pdf p4, annual-report-2023-en.pdf p9 | 1 | 39.7 s |
| D34 | en | overview, english, cross_document | answered | yes | - | gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | gep-enrolment-survey-2015.pdf p1, gep-enrolment-survey-2015.pdf p2, gep-enrolment-survey-2015.pdf p3, gep-enrolment-survey-2015.pdf p4, gep-donor-agreement-2019.pdf p1, gep-donor-agreement-2019.pdf p2, gep-donor-agreement-2019.pdf p3, gep-donor-agreement-2019.pdf p4, gep-donor-agreement-2019.pdf p5, gep-donor-agreement-2019.pdf p6, gep-midterm-evaluation-2020.pdf p1, gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p3, gep-midterm-evaluation-2020.pdf p4, gep-midterm-evaluation-2020.pdf p5, gep-midterm-evaluation-2020.pdf p6, annual-report-2016.pdf p3, annual-report-2016.pdf p5, annual-report-2016.pdf p6, annual-report-2020.pdf p5, annual-report-2020.pdf p8, annual-report-2020.pdf p11, annual-report-2021.pdf p5, annual-report-2021.pdf p14, annual-report-2022.pdf p5, annual-report-2022.pdf p9, annual-report-2022.pdf p13, annual-report-2023-en.pdf p4, annual-report-2023-en.pdf p9 | 1 | 41.2 s |
| D35 | ar | unanswerable, overview, colloquial | no_answer | yes | - | - | - | - | 5.1 s |
| D36 | en | unanswerable, overview | no_answer | yes | - | - | - | - | 5.5 s |
| D37 | en | unanswerable, near_miss, english | answered | no | invented_answer | annual-report-2023-en.pdf p8, spc-donor-agreement-2023.docx p2, spc-donor-agreement-2023.docx p3 | - | - | 36.9 s |
| D38 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 30.2 s |
| D39 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 29.3 s |

Failures:

- **D02** `false_refusal`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.999; best expected page at rank 2 (rerank 0.992, dense rank 4, lexical rank -)
- **D07** `page_split`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.995; best expected page at rank 1 (rerank 0.995, dense rank 1, lexical rank 2)
- **D37** `invented_answer`: outcome answered; band answer; top score 0.999

## Category rules

Each failure has one category, the first that applies: `error` (the request failed), `invented_answer` (an unanswerable question was answered, low confidence included), `page_split` (a page-split item failed), `false_refusal` (an answerable question was refused), `retrieval` (no expected page among the candidates), `generation` (an expected page was retrieved, but the facts or the citation are wrong), `unclassified` (retrieval or generation, but the server sent no candidates).
