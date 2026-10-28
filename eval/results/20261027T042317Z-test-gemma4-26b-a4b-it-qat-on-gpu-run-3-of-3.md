# Eval: test set, gemma4:26b-a4b-it-qat on GPU, run 3 of 3

**Score: 12/15**

| | |
|---|---|
| set | test |
| set_file | eval/questions.yaml |
| set_version | 2 |
| questions | 15 |
| only | - |
| date | 2026-10-27T04:23:17+00:00 |
| git_sha | d73ae1ef3a82-dirty |
| model | gemma4:26b-a4b-it-qat on GPU, run 3 of 3 |
| hardware | Intel Core i9-14900KF (24 cores, 32 threads), 32 GB RAM, RTX 5080 16 GB (NVIDIA 617.14), Windows 11 Pro 26300 with WSL2 Ubuntu 24.04, Docker Desktop 4.83.0 (Engine 29.6.2) with 12 CPUs and 23.5 GiB, GPU (containerised Ollama, docker-compose.gpu.yml) |
| ollama_version | 0.40.10 |
| server_llm_provider | unknown |
| server_llm_model | unknown |
| signed_in_as | editor (editor@sanad.example) |
| diagnostics_requested | True |
| base_url | http://api:8000 |
| runs | 1 |
| wall_seconds | 96.4 |

## Totals

- Score: 12/15
- Answerable correct: 9/12
- Refusal accuracy: 3/3 unanswerable refused; false refusals: 0
- Invented answers: 0
- recall@5: 12/12; recall@10: 12/12 (an expected page among the candidates)
- Latency, server total: median 6.5 s, p90 7.3 s (n=15)
- Latency, request wall time: median 6.5 s, p90 7.3 s (n=15)
- Failures by category: page_split 1, generation 2
- Stage `embed`: median 0.0 s, p90 0.0 s (n=15)
- Stage `first_token`: median 1.6 s, p90 1.8 s (n=14)
- Stage `generate`: median 2.0 s, p90 2.2 s (n=14)
- Stage `rerank`: median 4.7 s, p90 5.2 s (n=15)
- Stage `retrieve`: median 0.0 s, p90 0.0 s (n=15)
- Run wall time: 1 min 36 s

## Questions

| ID | Lang | Kinds | Outcome | Correct | Category | Cited pages | Expected pages | Rank | Latency |
|---|---|---|---|---|---|---|---|---|---|
| T01 | ar | factual, numeric | answered | yes | - | annual-report-2021.pdf p6 | annual-report-2021.pdf p6, annual-report-2021.pdf p7, yep-final-evaluation-2022.pdf p4 | 1 | 5.9 s |
| T04 | ar | factual, numeric | answered | yes | - | chp-household-survey-2021.pdf p3, annual-report-2021.pdf p11, chp-evaluation-2024.pdf p5 | chp-household-survey-2021.pdf p3, annual-report-2021.pdf p11, chp-evaluation-2024.pdf p5 | 1 | 6.6 s |
| T07 | ar | factual, numeric, mixed_content | answered | yes | - | spc-donor-agreement-2023.docx p2, board-minutes-2023-03.pdf p3 | spc-donor-agreement-2023.docx p2, spc-donor-agreement-2023.docx p3, board-minutes-2023-03.pdf p3, annual-report-2023-en.pdf p8 | 1 | 6.0 s |
| T09 | ar | factual, numeric, tatweel | answered | yes | - | annual-report-2021.pdf p9 | annual-report-2021.pdf p9 | 1 | 7.3 s |
| T10 | ar | factual, numeric, diacritics | answered | yes | - | annual-report-2021.pdf p3, annual-report-2021.pdf p4 | annual-report-2021.pdf p3, annual-report-2021.pdf p4 | 1 | 7.0 s |
| T12 | ar | factual, numeric | low_confidence | no | generation | budget-2018.docx p3 | budget-2018.docx p3 | 1 | 6.4 s |
| T13 | ar | factual, numeric | answered | no | generation | yep-tracer-survey-2023.pdf p3 | yep-tracer-survey-2023.pdf p3, annual-report-2023-en.pdf p5 | 1 | 6.0 s |
| T14 | ar | factual, numeric, page_split | no_answer | no | page_split | - | chp-evaluation-2024.pdf p5 | 3 | 6.4 s |
| T15 | ar | cross_document, temporal, numeric | answered | yes | - | wash-final-evaluation-2021.pdf p2, annual-report-2021.pdf p8, wash-final-evaluation-2021.pdf p4 | wash-baseline-survey-2017.pdf p3, wash-final-evaluation-2021.pdf p2, wash-final-evaluation-2021.pdf p4, annual-report-2021.pdf p8 | 1 | 6.8 s |
| T16 | ar | cross_document, temporal, numeric | answered | yes | - | yep-final-evaluation-2022.pdf p4, annual-report-2022.pdf p6 | annual-report-2020.pdf p6, annual-report-2022.pdf p6, yep-final-evaluation-2022.pdf p4 | 1 | 6.5 s |
| T18 | en | factual, numeric, english | answered | yes | - | gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | gep-midterm-evaluation-2020.pdf p2, gep-midterm-evaluation-2020.pdf p4 | 1 | 7.4 s |
| T19 | en | factual, numeric, english, cross_lingual | answered | yes | - | yep-final-evaluation-2022.pdf p5, yep-final-evaluation-2022.pdf p2 | yep-final-evaluation-2022.pdf p2, yep-final-evaluation-2022.pdf p5 | 1 | 7.2 s |
| T21 | ar | unanswerable, near_miss | no_answer | yes | - | - | - | - | 5.2 s |
| T23 | en | unanswerable, near_miss, english | no_answer | yes | - | - | - | - | 6.5 s |
| T24 | ar | unanswerable | no_answer | yes | - | - | - | - | 5.1 s |

Failures:

- **T12** `generation`: outcome low_confidence; band low_confidence; top score 0.259; missing facts 140,000; citation ok; best expected page at rank 1 (rerank 0.259, dense rank 1, lexical rank -)
- **T13** `generation`: outcome answered; band answer; top score 0.999; missing facts 64; citation ok; best expected page at rank 1 (rerank 0.999, dense rank 1, lexical rank -)
- **T14** `page_split`: outcome no_answer; refusal_reason sentinel; band answer; top score 0.996; best expected page at rank 3 (rerank 0.877, dense rank 4, lexical rank 13)

## Category rules

Each failure has one category, the first that applies: `error` (the request failed), `invented_answer` (an unanswerable question was answered, low confidence included), `page_split` (a page-split item failed), `false_refusal` (an answerable question was refused), `retrieval` (no expected page among the candidates), `generation` (an expected page was retrieved, but the facts or the citation are wrong), `unclassified` (retrieval or generation, but the server sent no candidates).
