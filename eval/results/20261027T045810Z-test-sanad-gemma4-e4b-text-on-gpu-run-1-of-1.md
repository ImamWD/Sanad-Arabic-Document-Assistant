# Eval: test set, sanad-gemma4-e4b-text on GPU, run 1 of 1

**Score: 12/15**

> **INVENTED ANSWERS: 1 (T23).** The system answered a question the documents can't answer. This is the failure the refusal gate exists to prevent.

| | |
|---|---|
| set | test |
| set_file | eval/questions.yaml |
| set_version | 2 |
| questions | 15 |
| only | - |
| date | 2026-10-27T04:58:10+00:00 |
| git_sha | 995681809480 |
| model | sanad-gemma4-e4b-text on GPU, run 1 of 1 |
| hardware | Intel Core i9-14900KF (24 cores, 32 threads), 32 GB RAM, RTX 5080 16 GB (NVIDIA 617.14), Windows 11 Pro 26300 with WSL2 Ubuntu 24.04, Docker Desktop 4.83.0 (Engine 29.6.2) with 12 CPUs and 23.5 GiB, GPU (containerised Ollama, docker-compose.gpu.yml) |
| ollama_version | 0.40.10 |
| server_llm_provider | unknown |
| server_llm_model | unknown |
| signed_in_as | editor (editor@sanad.example) |
| diagnostics_requested | True |
| base_url | http://api:8000 |
| runs | 1 |
| wall_seconds | 79.9 |

## Totals

- Score: 12/15
- Answerable correct: 10/12
- Refusal accuracy: 2/3 unanswerable refused; false refusals: 0
- Invented answers: 1 (T23)
- recall@5: 12/12; recall@10: 12/12 (an expected page among the candidates)
- Latency, server total: median 5.0 s, p90 6.2 s (n=15)
- Latency, request wall time: median 5.0 s, p90 6.2 s (n=15)
- Failures by category: invented_answer 1, page_split 1, generation 1
- Stage `embed`: median 0.0 s, p90 0.0 s (n=15)
- Stage `first_token`: median 0.4 s, p90 0.5 s (n=14)
- Stage `generate`: median 0.7 s, p90 0.9 s (n=14)
- Stage `rerank`: median 4.3 s, p90 5.0 s (n=15)
- Stage `retrieve`: median 0.0 s, p90 0.0 s (n=15)
- Run wall time: 1 min 20 s

## Questions

| ID | Lang | Kinds | Outcome | Correct | Category | Cited pages | Expected pages | Rank | Latency |
|---|---|---|---|---|---|---|---|---|---|
| T01 | ar | factual, numeric | answered | yes | - | annual-report-2021.pdf p6 | annual-report-2021.pdf p6, annual-report-2021.pdf p7, yep-final-evaluation-2022.pdf p4 | 1 | 4.5 s |
| T04 | ar | factual, numeric | answered | yes | - | chp-household-survey-2021.pdf p3, annual-report-2021.pdf p11 | chp-household-survey-2021.pdf p3, annual-report-2021.pdf p11, chp-evaluation-2024.pdf p5 | 1 | 5.3 s |
| T07 | ar | factual, numeric, mixed_content | answered | yes | - | spc-donor-agreement-2023.docx p2, board-minutes-2023-03.pdf p3 | spc-donor-agreement-2023.docx p2, spc-donor-agreement-2023.docx p3, board-minutes-2023-03.pdf p3, annual-report-2023-en.pdf p8 | 1 | 9.7 s |
| T09 | ar | factual, numeric, tatweel | answered | yes | - | annual-report-2021.pdf p9 | annual-report-2021.pdf p9 | 1 | 5.4 s |
| T10 | ar | factual, numeric, diacritics | answered | yes | - | annual-report-2021.pdf p3, annual-report-2021.pdf p4 | annual-report-2021.pdf p3, annual-report-2021.pdf p4 | 1 | 4.7 s |
| T12 | ar | factual, numeric | low_confidence | no | generation | budget-2018.docx p3 | budget-2018.docx p3 | 1 | 4.5 s |
| T13 | ar | factual, numeric | answered | yes | - | yep-tracer-survey-2023.pdf p3 | yep-tracer-survey-2023.pdf p3, annual-report-2023-en.pdf p5 | 1 | 4.6 s |
| T14 | ar | factual, numeric, page_split | no_answer | no | page_split | - | chp-evaluation-2024.pdf p5 | 3 | 4.7 s |
| T15 | ar | cross_document, temporal, numeric | answered | yes | - | wash-final-evaluation-2021.pdf p2, annual-report-2021.pdf p8, wash-final-evaluation-2021.pdf p4 | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p4, annual-report-2021.pdf p8 | 1 | 5.2 s |
| T16 | ar | cross_document, temporal, numeric | answered | yes | - | yep-final-evaluation-2022.pdf p4, annual-report-2022.pdf p6 | annual-report-2020.pdf p6, annual-report-2022.pdf p6, yep-final-evaluation-2022.pdf p4 | 1 | 4.6 s |
| T18 | en | factual, numeric, english | answered | yes | - | gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | 1 | 5.8 s |
| T19 | en | factual, numeric, english, cross_lingual | answered | yes | - | yep-final-evaluation-2022.pdf p5, yep-final-evaluation-2022.pdf p2, yep-tracer-survey-2023.pdf p4 | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p5 | 1 | 5.4 s |
| T21 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 4.1 s |
| T23 | en | unanswerable, near_miss, english | answered | no | invented_answer | gep-midterm-evaluation-2020.pdf p4, gep-donor-agreement-2019.pdf p3, annual-report-2022.pdf p9 | - | - | 6.2 s |
| T24 | ar | unanswerable | no_answer | yes | - | - | - | - | 5.0 s |

Failures:

- **T12** `generation`: outcome low_confidence; band low_confidence; top score 0.259; missing facts 140,000; citation ok; best expected page at rank 1 (rerank 0.259, dense rank 1, lexical rank -)
- **T14** `page_split`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.996; best expected page at rank 3 (rerank 0.877, dense rank 4, lexical rank 13)
- **T23** `invented_answer`: outcome answered; band answer; top score 0.998

## Category rules

Each failure has one category, the first that applies: `error` (the request failed), `invented_answer` (an unanswerable question was answered, low confidence included), `page_split` (a page-split item failed), `false_refusal` (an answerable question was refused), `retrieval` (no expected page among the candidates), `generation` (an expected page was retrieved, but the facts or the citation are wrong), `unclassified` (retrieval or generation, but the server sent no candidates).
