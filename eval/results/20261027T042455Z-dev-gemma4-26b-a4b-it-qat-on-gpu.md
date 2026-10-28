# Eval: dev set, gemma4:26b-a4b-it-qat on GPU

**Score: 1/1**

| | |
|---|---|
| set | dev |
| set_file | eval/dev_questions.yaml |
| set_version | 4 |
| questions | 1 |
| only | D37 |
| date | 2026-10-27T04:24:55+00:00 |
| git_sha | d73ae1ef3a82 |
| model | gemma4:26b-a4b-it-qat on GPU |
| hardware | Intel Core i9-14900KF (24 cores, 32 threads), 32 GB RAM, RTX 5080 16 GB (NVIDIA 617.14), Windows 11 Pro 26300 with WSL2 Ubuntu 24.04, Docker Desktop 4.83.0 (Engine 29.6.2) with 12 CPUs and 23.5 GiB, GPU (containerised Ollama, docker-compose.gpu.yml) |
| ollama_version | 0.40.10 |
| server_llm_provider | unknown |
| server_llm_model | unknown |
| signed_in_as | editor (editor@sanad.example) |
| diagnostics_requested | True |
| base_url | http://api:8000 |
| runs | 1 |
| wall_seconds | 6.0 |

## Totals

- Score: 1/1
- Answerable correct: 0/0
- Refusal accuracy: 1/1 unanswerable refused; false refusals: 0
- Invented answers: 0
- recall@5 and recall@10: n/a (the server sent no candidates)
- Latency, server total: median 5.9 s, p90 5.9 s (n=1)
- Latency, request wall time: median 5.9 s, p90 5.9 s (n=1)
- Failures by category: none
- Stage `embed`: median 0.0 s, p90 0.0 s (n=1)
- Stage `first_token`: median 1.4 s, p90 1.4 s (n=1)
- Stage `generate`: median 1.4 s, p90 1.4 s (n=1)
- Stage `rerank`: median 4.4 s, p90 4.4 s (n=1)
- Stage `retrieve`: median 0.0 s, p90 0.0 s (n=1)
- Run wall time: 6 s

## Questions

| ID | Lang | Kinds | Outcome | Correct | Category | Cited pages | Expected pages | Rank | Latency |
|---|---|---|---|---|---|---|---|---|---|
| D37 | en | unanswerable, near_miss, english | no_answer | yes | - | - | - | - | 5.9 s |

Failures:

- none

## Category rules

Each failure has one category, the first that applies: `error` (the request failed), `invented_answer` (an unanswerable question was answered, low confidence included), `page_split` (a page-split item failed), `false_refusal` (an answerable question was refused), `retrieval` (no expected page among the candidates), `generation` (an expected page was retrieved, but the facts or the citation are wrong), `unclassified` (retrieval or generation, but the server sent no candidates).
