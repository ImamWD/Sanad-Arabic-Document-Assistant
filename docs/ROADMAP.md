# Roadmap and executor task briefs

**How we work**
- The project manager (Claude, this session) plans, reviews and verifies. Executor Claude Code agents implement.
- Each task below is self-contained. Before starting, an executor reads [`CLAUDE.md`](../CLAUDE.md), [`brief.md`](brief.md), [`DECISIONS.md`](DECISIONS.md) (the client's approved decisions, which win over the brief), [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md), and its own brief.
- Each executor works on a local branch `task/<ID>-<slug>`.
  - **Push hold:** no pushes and no PRs until the owner lifts the hold (OPEN_QUESTIONS P0).
  - Until then, the executor's final report *is* the PR description.
- The manager re-runs the **Verify** commands, reviews the diff against the acceptance criteria, and merges locally only when they pass.
- No task is "done" on the executor's word alone.

## Timeline (8-week build, then GPU cutover)

> **Provisional.** On 24 Oct the owner asked the client for their overall deadline and expected durations (OPEN_QUESTIONS N7). Until they answer, the dates below are our assumption.

This follows the client's phasing (DECISIONS D3): build and demonstrate on CPU in weeks 1–8, and have the GPU in place **before 31 January**. Week 1 is assumed to start on **Mon 26 Oct 2026** (N6).

Executor tasks usually take hours to a day of agent time. Elapsed time is driven by the manager's verification, by integration, and by inputs from the client.

| Week | Dates | Build | Client-facing |
|---|---|---|---|
| 1 | 26 Oct – 1 Nov | ✅ M0 (verified; merging after code review). C1a, then C1b. Start S1, S2, S3, S4, B1, F1. | Manager: GPU research and RFQ draft; choose the free reference API. **Ask the client for N1 (server details) by 31 Oct.** |
| 2 | 2 – 8 Nov | Spike reports. B2 (schema and auth). F2 against a mocked stream. G1 GPU benchmark kit, plus the rented run if the owner approves it (P4). | **Deliverables 1–2**, if N1 and the rental are available. Client sends the 8 sample reports (N5). |
| 3 | 9 – 15 Nov | B3 (ingestion and `ml`). R1 (ask, never-frozen stream, outcome summary). F3 (Library and Upload). | — |
| 4 | 16 – 22 Nov | Integration. First E1 run, including the page-split failure category. | **Week-4 demo, on CPU**: guest or login → upload with live status → Arabic question → streamed answer with stages → citation → viewer at the page. **Deliverable 3.** The manager drafts an Arabic and English note for demo users ("answers take 30–90 s until the GPU arrives; the screen shows progress"), and the owner sends it. |
| 5 | 23 – 29 Nov | F4 (paragraph highlight, version history, smoke test). F5 (Admin and outcome summary). Remaining E1 reports (model gap, `--repeat`). | — |
| 6 | 30 Nov – 6 Dec | E2 tuning on the **dev** set only. Fixes from week-4 feedback. | — |
| 7 | 7 – 13 Dec | H1 (50-file batch). H2 (clean machine and egress). H4 preparation: bulk import, GPU override, runbook. Deployment dry run on a CPU server like the client's. | — |
| 8 | 14 – 20 Dec | Release candidate frozen. E2 headline runs. H3 (README and acceptance run). | **Week-8 demo**: feature-complete. **Deliverables 5, 6 and 7.** The demo-user note is sent again. |
| Jan | before 31 Jan | **H4**: install on the client server, enable the GPU, first full archive ingestion (run by the owner or the client's IT), speed check on the real card. | **Deliverable 4.** Final acceptance (date per N7). |

**Risks to the dates**
- **Board timing.** The client's board approves capital purchases once a quarter. If deliverable 1 misses the next meeting (N2), the purchase can slip by up to a quarter, and the 31 January GPU date is lost.
  - Mitigation: get N1 by 31 Oct, send the RFQ the day N1 arrives, and ask suppliers for their lead time to Nablus or Ramallah, including customs.
- **GPU lead time.** Professional cards are reported at up to ~2 months, and no West Bank retailer stocks them. They come through an importer or the server vendor's partner. To be installed before 31 January, the order must be placed in **November**. Prices are rising, so the quote needs a validity date that covers the board meeting.
- The sample reports or the server details arrive late. Deliverables 1, 2, 3 and 5 slip by the same amount.
- Real PDFs reveal extraction problems that the synthetic ones hide. S1 exists to find these in weeks 1–2, not in week 7.
- Eval runs on CPU take about 25 × 60 s ≈ 25 min each. That's fine overnight, but plan the E2 sweeps around it, or run them on the rented GPU.

## Client deliverables

| # | Deliverable | Due | Produced by | Status |
|---|---|---|---|---|
| 1 | Background: `docs/research/2026-10-24-gpu-and-hosted-apis.md`. **One figure in writing, not a range.** It names the card model and gives the installed total in the client's currency: card, VAT and customs, installation, and any PSU, cabling or cooling. It names the supplier, has a validity date that covers the board meeting and the purchase, and gives the delivery lead time. Online prices are background only and never presented as the number. A second card appears only as a labelled fallback, also as a single figure. | Before the client's next board meeting (N2); target 8 Nov | Manager research and RFQ draft → owner sends the RFQ and collects the written quote | Research done; RFQ drafted; blocked on N1 |
| 2 | **Measured** time per answer on that card class: full pipeline, p90 and median, on synthetic data. If no card can be rented, a clearly marked estimate. | With #1 | G1 (rental needs P4) | Not started |
| 3 | Page-split rate (paragraphs cut by a page break) on the 8 sample reports (aggregate only) and on the synthetic corpus, plus any synthetic eval failures it causes | Week 4 | S1 metric + E1 page-split category | Waiting for samples |
| 4 | Count of scanned (no text layer) files in the archive | First full run, before 31 Jan | H4 bulk import + B3 ingestion summary, run by the owner or the client's IT | — |
| 5 | Highlight success rate on the 8 real reports, reported separately from synthetic | Week 8 | F4 highlight-rate script (the owner runs the real-report part, per N4) | — |
| 6 | Refused / low-confidence / answered counts in the Admin log, refusals split by reason | Week 8 | R1 `/admin/usage/summary` + F5 | — |
| 7 | Headline score on the **production model**; if the CPU demo model differs, its score and the gap | Week 8 | E1 `--model` + E2 headline runs | — |

## Tracks and order

```
              ┌─ S1 extraction ─┐
M0 ──────────►├─ S2 embeddings ─┼──► B3 ingestion ──► R1 ask ──► E1 eval ──► E2 tuning ──► H1–H4
 (foundation) ├─ S3 local LLM ──┼──► G1 GPU bench    ▲                                     ▲
              ├─ S4 viewer ─────┘                    │                                     │
              ├─ B1 arabic lib ──► B2 schema/auth ───┘                                     │
              └─ F1 shell ──► F2 ask ─► F3 library/upload ─► F4 viewer ─► F5 admin ────────┘
C1a corpus + eval authoring (text only) ── day 1 ──► C1b render + check (after M0) ──► feeds S1–S4, G1, E1
```

**Waves**
- Wave 0, day 1: M0 and C1a, in parallel.
- Wave 1, after M0: C1b first (its early drop unblocks the spikes), then S1, S2, S3, S4, B1 and F1.
- Wave 2: B2, F2 (against a mocked stream), and G1 once S3 picks the models.
- Wave 3: B3, R1 and F3.
- Wave 3b, after B3's version endpoints and R1's summary: F4 and F5.
- Wave 4: E1 (first run as soon as R1 merges), then E2.
- Wave 5: H1, H2 and H3. Then H4 in January.

**File ownership.** Writers never share files, with two exceptions.

The **shared append-only files** below may be edited by any task, but only by *adding*: keys, settings, codes, router lines, matrix rows or dependencies. The manager merges them in a fixed order (B3, R1, then F2–F5) and resolves conflicts.
- `frontend/src/locales/ar.json` and `en.json` (add keys, always both files)
- `.env.example` (add settings, each with a comment)
- `backend/sanad/core/errors.py` (add error codes)
- the router registration list in `backend/sanad/api/main.py` (one line per router)
- the permission-matrix table in `backend/tests/api/test_permissions.py` (add rows for your routes)
- **dependency manifests:**
  - `backend/pyproject.toml`, `ml/pyproject.toml` and `frontend/package.json`: add a dependency only, pinned exactly, and list it in your report
  - their lockfiles: commit your regenerated lock; on conflict the manager re-locks with `make lock` at merge

**Container and compose files** have explicit owners:

| File or service | Owner |
|---|---|
| `docker-compose.dev.yml`, per-worktree instance naming, tool-container mounts | M0b (the M0 follow-up) |
| `init` service; the Alembic `COPY` in `backend/Dockerfile` | B2 |
| LibreOffice and Arabic fonts in `backend/Dockerfile` (worker image) | B3 |
| `ollama` and `ollama-init` services, `docker-compose.api-llm.yml`, stream settings in `deploy/nginx.conf` | R1 |
| `docker-compose.gpu.yml` | H4 |
| `docker-compose.samples.yml`, if needed (the owner-only stack for the client samples; see CLAUDE.md) | S1 |

Throughout, *Verify* means the exact commands the manager will run. Executors run them first and paste the output into their report.

---

## M0 — Foundation ✅

### M0 · Scaffold, compose skeleton, lint gates
**Status.** Built on `task/M0-scaffold`.
- The manager re-ran every Verify command on 24 Oct, and all pass.
- An extra probe with an inline style of `marginLeft` is also caught.

Merging into `main` waits for the code-review findings.

**Scope (as delivered)**
- Compose services `db`, `api` (health only), `worker` (idle), `ml` (stub), `web` (nginx + Vite build).
- Dev images `backend-dev` and `ml-dev`, plus the `node`, `e2e` and `render` tool containers.
- `backend` network `internal: true`. `web` is the only published port.
- Lint gates for i18n literal strings, physical CSS, inline physical styles and inline-disable bans, each with a self-test.
- `make` targets: `up`, `down`, `lint`, `test`, `test-frontend` (vitest), `test-e2e` (Playwright on the running stack), `fmt`, `gen-api-types`.
- A CI workflow. It has never run on GitHub, because of the push hold.

**Notes for later tasks**
- Python tests run in `backend-dev`, never in the slim `api` image.
- The compose project name is fixed to `sanad`, so parallel stacks need `-p <name>`.

---

## Spikes (time-boxed; each produces a report in `docs/spikes/Sx-*.md` plus a runnable script)

**Rules for every spike**
- Public downloads follow P2:
  - Commit a manifest (`spikes/<id>/downloads.json` with the URL, sha256 and licence of each file) and a `fetch.py`.
  - Files go into `spikes/_downloads/`, which is git-ignored.
  - Delete them **after the manager's verification**.
- Model weights pulled for a spike go only into the git-ignored `/models/` or `/hf_cache/` folders, or a named Docker volume. Models that weren't chosen are removed at the end (`ollama rm …`, delete cache entries), and the report lists them.

### S1 · Arabic PDF text extraction
**Scope.**
- Compare `pypdfium2`, `PyMuPDF` and `pdfminer.six` on three sets:
  - (a) the C1 seed PDFs
  - (b) at least 5 public real-world Arabic PDFs (P2)
  - (c) the client's **8 sample reports** in `data/client-samples/`, once they arrive
- **Client samples are aggregate-only (N4).**
  - Never open, print or read their text, titles or file names.
  - Only run scripts whose output is numbers, written so they never echo document text, even in errors.
  - Anything that needs eyes is listed for the owner.
- Measure:
  - correct logical order (automatic proxy: the share of extracted Arabic tokens found in a wordlist, compared with the same text reversed)
  - presentation-form folding
  - lam-alef
  - Arabic-Indic digits
  - Latin codes and URLs inside Arabic sentences
  - tables
  - speed
  - licence
- **Page-split metric (deliverable 3).**
  - Run it after removing running headers, footers and page numbers.
  - A page break *splits a paragraph* when both of these hold:
    - the last text line of page N doesn't end in sentence-final punctuation (`. ؟ ? ! :`) and is not a heading, table row or list item
    - the first line of page N+1 is not a heading and doesn't start with a list marker
  - Report per set: (a) splits ÷ page breaks, and (b) split paragraphs ÷ all paragraphs.
  - Arabic has no letter case, so case can't be used as a signal.
  - The owner checks about 10 flagged breaks in the client samples by eye (N4 c).
- Specify the visual-order detection and repair heuristic, and the `NO_TEXT_LAYER` thresholds.

**Owns.** `docs/spikes/S1-extraction.md`, `spikes/s1/`.

**Acceptance**
- A per-PDF comparison table for sets (a) and (b), and aggregate-only numbers for (c).
- A recommendation with its licence implications.
- The page-split rates per set.
- The cleaning rules as test cases ready for B1.
- The download manifest.

**Verify**
```
docker compose run --rm backend-dev sh -c "python spikes/s1/fetch.py && python spikes/s1/compare.py seed/documents spikes/_downloads"
docker compose run --rm backend-dev python spikes/s1/aggregate.py data/client-samples   # the owner runs this; prints numbers only
```

### S2 · Embedding and reranker shoot-out
**Scope.**
- Compare `bge-m3` (the client-approved default), `multilingual-e5-large` and `gte-multilingual-base`, and confirm `bge-reranker-v2-m3`.
- Use the C1 dev questions (about 20 question→page pairs).
- Measure:
  - recall@5 and recall@10, dense alone and with the reranker
  - CPU throughput in chunks per second (arm64 measured, x86 estimated)
  - memory use
  - licence
- Try ONNX or int8 builds for CPU speed.

**Owns.** `docs/spikes/S2-embeddings.md`, `spikes/s2/`.

**Acceptance.** A recommendation with numbers, the inputs for D2's cost table, and a list of removed models.

**Verify.** `docker compose run --rm backend-dev python spikes/s2/run.py --quick` reproduces the recall table on the dev set.

### S3 · Local LLM shoot-out
**Scope.**
- Candidates: about 5 Ollama models (a Qwen 7B and a 14B instruct, Gemma ~12B, ALLaM 7B or another Arabic-tuned model, and `gemma4:31b` as a stretch candidate for a 24–32 GB card; check each licence).
  - `gemma4:31b` is also available on the free Gemini API tier as `gemma-4-31b-it`, so its hosted and local scores can be compared directly.
- Run 10 fixed RAG prompts with Arabic excerpts from the seed corpus, 3 of them unanswerable.
- Score:
  - follows "excerpts only"
  - emits `[n]` markers
  - emits `NO_ANSWER` correctly
  - Arabic fluency (rubric)
  - prompt-processing and generation speed on CPU in a container (host Metal for reference)
  - RAM
- Recommend two models:
  - the **production model**, the best quality expected to meet p90 ≤ 15 s on a 24 GB GPU
  - the **CPU demo model** for weeks 1–8, which can be the same model
- A **free hosted reference model** runs the same synthetic prompts through `openai_compat`, using the Google Gemini API free tier (P3/P5): `gemini-3.1-flash-lite` and `gemma-4-31b-it`.
  - Free-tier prompts are used for training, so send synthetic data only.
  - Pin model IDs, and record the provider, model and date with every result.

**Owns.** `docs/spikes/S3-local-llm.md`, `spikes/s3/`.

**Acceptance.** A ranked table, the two model recommendations, the inputs for D3, and a list of removed models.

**Verify.** `docker compose run --rm backend-dev python spikes/s3/run.py --model <recommended> --prompts 3` reproduces scores for 3 prompts.

### S4 · Viewer highlight and DOCX fidelity
**Scope.**
- Build a pdf.js prototype that opens page N and highlights a span by matching normalised text against the text layer.
- Measure the success rate on the seed PDFs and on public Arabic PDFs (P2). **Never on the client samples**; their rate is deliverable 5 (F4).
- Convert 3 Arabic DOCX files through LibreOffice headless in the worker image and check font shaping.

**Owns.** `docs/spikes/S4-viewer.md`, `spikes/s4/`.

**Acceptance.** The success rate, the failure modes, and the font packages for the worker image.

### G1 · GPU benchmark kit (deliverable 2)
Background is in `docs/research/2026-10-24-gpu-and-hosted-apis.md` §2.

**Scope.**
- **What runs on the pod.** RunPod and Vast.ai pods can't run Docker Compose or Docker-in-Docker. So the rented machine runs only the plain `ollama/ollama` image, with a pinned Ollama version and pinned model tags.
- **What runs locally.** A replay script in `spikes/g1/` sends the 25 assembled headline prompts to the pod over HTTPS, with streaming on and an explicit `num_ctx`.
  - Timings come from Ollama's own response fields (`load_duration`, `prompt_eval_*`, `eval_*`), plus time to first token.
  - It does one warm-up, then two runs per question per model.
  - It logs `nvidia-smi` name, power limit, clocks and driver with every result.
- **No client data** goes anywhere.
- **Prompts.** R1 doesn't exist in week 2, so prompts are built the way R1 will build them: the system prompt plus each question's expected-citation pages and neighbouring seed chunks, about 4k tokens in total. The report says they are approximations. Once R1 merges, the script can call `POST /api/ask` for a confirmation run.
- **Full-pipeline total.** Embedding, retrieval and rerank are timed separately (`ml` on CPU locally, and on GPU if a host allows a second container) and added to the LLM time. The report shows each stage and the total.
- **Target definition:** met when **p90 total time per answer ≤ 15 s**. The median is also reported.
- **Cards** (three, bracketing the decision):
  - the RTX PRO 4000 Blackwell (the likely purchase; Vast, verified host)
  - an L4 (the floor; RunPod Secure)
  - an RTX 4090 with power limit ≥ 450 W (the ceiling)

  Each runs the S3 production model and the CPU demo model.
- **Cost and approval.** About $5 of GPU time, a $10 budget and $15 up front (P4). **The rental is a paid action and needs the owner's approval.** The executor prepares and documents the run, and the owner rents the cards. Afterwards every instance and its disk are **destroyed**, and the report confirms this.

**Owns.** `spikes/g1/`, `docs/spikes/G1-gpu-benchmark.md`.

**Acceptance.** A one-page result for the client: card, models, per-stage and total median and p90, and whether the target is met. Every number is labelled measured or estimated, and no rented-card result is presented as another card's.

**Verify.** `docker compose run --rm backend-dev python spikes/g1/replay.py --target http://<local ollama> --questions 3`. The script must also work against a local CPU Ollama. The manager reviews the logs from the rented runs.

---

## C1 · Seed corpus and evaluation set (content track)

**Split by dependency**
- **C1a starts on day 1.** It is pure authoring with no containers: `seed/README.md`, `seed/manifest.json`, `seed/sources/**`, `eval/questions.yaml` and `eval/dev_questions.yaml`.
- **C1b runs after M0.** It renders the sources to PDF, DOCX and TXT, builds `seed/bad/`, and writes and runs the checker.
- **Early drop:** about 8 documents plus the dev questions first.

**Scope.**
- **Organisation.** A fictional stand-in, مؤسسة الريحان للتنمية / Al-Rayhan Development Foundation. Never the client's real name.
- **Programmes.** 6 fictional programmes with bilingual names.
- **Documents.** About 30, spanning 2015–2025:
  - categories: annual reports, donor agreements, evaluations, surveys, budgets, board minutes
  - languages: about 80% Arabic, about 15% English, a few mixed
  - formats: about 24 PDF, 4 DOCX, 2 TXT (one in Windows-1256)
  - length: 3–20 pages each
  - content: numeric tables, project codes and URLs inside Arabic sentences, some diacritics and tatweel
  - one budget draft/final version pair
  - all personal data **obviously synthetic**
- **Page-split coverage (deliverable 3).** At least 2 dev or headline facts sit in a paragraph that crosses a page break. The cited page is the page where the fact appears.
- **Failure fixtures** in `seed/bad/`: a truncated PDF, a password-protected PDF, an image-only PDF, an empty DOCX, and a `.exe` renamed to `.pdf`.
- **Eval sets.**
  - `eval/questions.yaml`: the 25 headline questions (`--set test`).
  - `eval/dev_questions.yaml`: 15–20 tuning questions (`--set dev`), with no overlap.
- **Eval honesty.**
  - Headline questions paraphrase their source.
  - At least 8 of the 25 use vocabulary that differs from the page.
- No lorem ipsum, no `test1`.

**C1b implementation notes (from M0)**
- Render with Noto Naskh Arabic or Amiri. Don't use KacstOne: text extraction turns its lam-meem ligature into the wrong letters.
- Produce DOCX with python-docx or pandoc, not LibreOffice HTML → DOCX.
- Check whether LibreOffice breaks TXT pages at form feeds.
- Add `pypdfium2` and `PyYAML` to the `dev` dependency group.

**Owns.** `seed/`, `eval/*.yaml`, `scripts/check_eval.py`. C1b also owns the dev-dependency lines in `backend/pyproject.toml` and `backend/uv.lock`.

**Acceptance**
- Every PDF shows correctly shaped Arabic, with screenshots of 3 pages.
- `scripts/check_eval.py` confirms that every `must_include` fact is on its expected page: 100% before merge.
- Five headline questions are unanswerable, two of them near-misses.
- At least two facts are in page-crossing paragraphs.

**Verify.** `docker compose run --rm backend-dev python scripts/check_eval.py eval/questions.yaml eval/dev_questions.yaml`

---

## Backend

### B1 · Arabic text library (`backend/sanad/text/arabic.py`)
**Scope.** Pure functions with no I/O:
- `normalize_for_search`:
  - strip tashkeel (U+064B–U+0652, U+0670) and tatweel (U+0640)
  - unify أ إ آ ٱ → ا, ى → ي, ؤ → و, ئ → ي, and (configurable) ة → ه
  - map Arabic-Indic and Persian digits to Latin
  - NFKC
  - lowercase Latin
  - collapse whitespace
- `clean_extracted`: presentation forms, bidi controls, visual-order repair (S1), header and footer removal.
- `detect_language`.
- `split_sentences` (`؟ ، ؛ .`).
- `ARABIC_STOPWORDS` and `lexical_terms(question)`.
- Optional `strip_clitics` (an E2 sweep variant only).
- `normalize_number_tokens`.

**Owns.** `backend/sanad/text/`, `backend/tests/text/`.

**Acceptance.** 100% branch coverage. Required cases:
- `normalize_for_search("التعليــم") == normalize_for_search("التعليم")`
- the diacritised form `"التَّعْلِيم"` matches as well
- alef and hamza variants
- presentation-form input
- `YEP-2021-03` kept intact inside Arabic

**Verify.** `docker compose run --rm backend-dev pytest backend/tests/text -q --cov=sanad.text --cov-fail-under=100`

### B2 · Schema, migrations, auth, roles, users, programmes
**Scope.**
- Alembic migrations for SYSTEM_DESIGN §4, including:
  - `refusal_reason`
  - the version fields
  - `amends_document_id` and `amendment_no` (nullable; N3)
  - `index_generation`
  - `llm_perf_samples`
- The `init` service: migrations, then seed the admin, editor, viewer and guest users and the programmes, then register the seed documents as `queued` with `is_seed=true`.
- Auth: argon2id, session cookie, guest login, rate limiting.
- Role guards.
- `/me`, `/admin/users`, `GET /programmes`.
- The error-code registry and its translation test.

**Owns.** `backend/sanad/{core,api/auth.py,api/me.py,api/admin_users.py,api/programmes.py}`, `backend/alembic/`, `backend/tests/api/`, the `init` service.

**Acceptance**
- **Permission matrix.** `backend/tests/api/test_permissions.py` is a table of role × route covering every route that exists at merge time, for all three roles plus guest. Later tasks add their own rows.
- With `GUEST_MODE=seed_only`, the guest gets 404 for a non-seed document.
- A deactivated user's session is rejected.
- **Approved wording is locked.** A test asserts that the refusal and low-confidence strings in `ar.json` and `en.json` equal the D4 approved text exactly, and that `errors.NO_TEXT_LAYER` says "This file has no text layer (scanned image)." with the approved Arabic.

**Verify.** `docker compose run --rm backend-dev pytest backend/tests/api -q`

### B3 · Ingestion pipeline and `ml` service
**Scope.**
- **Upload:** magic-byte check, size limit, sha256 duplicate check, plus `replaces_document_id` (new version) or `amends_document_id` (linked amendment, never supersedes).
- **Worker:** claim loop and stale-claim recovery; DOCX/TXT → PDF; extract, clean, chunk (D1 parameters from config), embed, store; error codes per SYSTEM_DESIGN §5.2.
- Retry, archive and unarchive endpoints; supersede on ready.
- **Version metadata:** `version`, `is_current` and `version_count` on every document object, in both list and detail responses. `include_superseded` on the list (default false). `GET /documents/{id}/versions`, which includes linked amendments with `kind: version | amendment`.
- **Re-indexing** writes a new `index_generation` of chunks and switches retrieval to it atomically. It never creates a user-visible version, and old chunks stay while citations point at them.
- **`ingestion_summary` report:** `python -m sanad.reports.ingestion_summary` prints counts by status and `error_code`. `NO_TEXT_LAYER` is the scanned-file count. It prints numbers and codes only.
- **Real `ml` service:** `/embed` and `/rerank` using the S2 choice, with weights baked in at build time and offline at runtime.

**Owns.** `backend/sanad/ingest/`, `backend/sanad/reports/`, `backend/sanad/api/documents.py`, `ml/`, `backend/tests/ingest/`.

**Acceptance**
- Every `seed/bad/*` fixture becomes `failed` with the correct code, and no stack trace appears in any response.
- The seed corpus reaches `ready` on first boot.
- A killed worker recovers on restart.
- Chunk page numbers match the viewer PDF.
- `replaces_document_id` sets `superseded_by` only once the new version is `ready`. A failed new version never supersedes.
- `/versions` lists every version and amendment.
- `ingestion_summary` on seed + bad prints `NO_TEXT_LAYER: 1` and no titles.

**Verify**
```
make up && docker compose run --rm backend-dev pytest backend/tests/ingest -q
docker compose run --rm backend-dev python -m sanad.reports.ingestion_summary
```

---

## Retrieval and answering

### R1 · Ask pipeline
**Scope.**
- **Retrieval:** dense plus lexical, RRF, rerank, and the three-band gate (D4).
  - The lexical query is an **OR of `lexical_terms()`**, ranked with `ts_rank_cd`. Never `plainto_tsquery` on the raw question.
- **Providers:**
  - `ollama` (temperature 0)
  - `openai_compat` (the free hosted reference, P3)
  - `anthropic` (official SDK, optional, no key needed to build or test). Load the `claude-api` skill before writing it, and don't send `temperature`, `top_p` or `top_k`.
- **Hosted-provider guard.** Hosted providers make **no call**, returning `HOSTED_LLM_NON_SEED_DATA`, if any excerpt comes from a document with `is_seed = false`. This is enforced in code and tested.
- **Prompting and validation:**
  - system prompt with the `NO_ANSWER` sentinel and an injection guard
  - marker validation
  - citations with `file_type` and `is_converted`
  - refusals carry up to 3 `nearest_documents`
  - `refusal_reason` set to `gate`, `sentinel` or `no_valid_citation`
  - persistence
- **Never-frozen stream (SYSTEM_DESIGN §6).** Events arrive in order: `queued` (when waiting), `searching`, `reading` (with `band`), `eta`, `writing` on the first token, `token`…, `final`.
  - The server holds back the first characters until the `NO_ANSWER` sentinel is ruled out.
  - `final` replaces the streamed text.
  - SSE headers include `X-Accel-Buffering: no`, with a `: ping` every 15 s.
  - Generation is queued under `LLM_MAX_CONCURRENCY`, and the ETA includes the requests ahead in the queue.
  - Every answer records an `llm_perf_samples` row.
- **Endpoints:** `POST /ask`, `POST /ask/stream`, `GET /queries`, `GET /admin/usage` and `GET /admin/usage/summary` (all four outcomes, refusals split by reason, most-refused questions grouped by normalised text).
- **Compose:** the `ollama` and `ollama-init` services (pulling `OLLAMA_MODELS`: the production model and the CPU demo model), `docker-compose.api-llm.yml` (attaches only `api` to `egress`), and the stream settings in nginx. `docker-compose.dev.yml` comes from M0b.
- **Settings:** the LLM and ETA settings go into config and `.env.example` (append-only).

**Owns.** `backend/sanad/{retrieval,llm}/`, `backend/sanad/api/{ask,queries,admin_usage}.py`, `backend/tests/retrieval/`, the compose items above.

**Acceptance**
- **Fake-LLM unit tests:**
  - out-of-range markers are dropped
  - no valid marker ⇒ `no_answer` (`no_valid_citation`)
  - the sentinel ⇒ `no_answer` (`sentinel`), and **no `token` events** are sent
  - below `T_refuse`, the LLM is never called (`gate`)
- **Stream test, slow fake LLM:**
  - `searching` and `reading` arrive before the first token
  - `reading` carries `band`
  - `eta` arrives before `writing`
  - a refusal never emits `writing`
  - a second concurrent request gets `queued`, with an ETA that includes the first
  - the response has `X-Accel-Buffering: no`
- **Guard:** with `openai_compat` set and a non-seed document in retrieval, no outbound call is made.
- **Integration:** one Arabic and one English seed question are answered with correct citations.
- **Prompt injection:** a seed document containing "ignore previous instructions…" doesn't change behaviour.
- **Egress:** with the base compose file, a hosted call fails with `LLM_UNREACHABLE`. With the api-llm override it succeeds. `ollama` has no egress.
- **Summary:** counts match the fixture queries.

**Verify**
```
docker compose run --rm backend-dev pytest backend/tests/retrieval -q
curl -N -X POST localhost:8080/api/ask/stream ...   # as guest, with an Arabic question; events must arrive in the order above
```

---

## Frontend

**Verify for F1–F5**
- Every task runs `make lint && make test-frontend && make up && make test-e2e`.
- Playwright runs in the `e2e` tools container, never on host Node.
- Each task's own specs: `docker compose run --rm e2e npx playwright test e2e/<feature>-*.spec.ts`.
- From F4 onward, the smoke test (login → Arabic question → first citation → viewer on the expected page, ≤2 clicks after login) is required too.

### F1 · App shell
**Scope.**
- Router, TanStack Query, i18next (`ar.json`, `en.json`), `dir`/`lang` sync and `?lang=` (already in M0).
- Radix `DirectionProvider`.
- `useFormat()` (Intl).
- `src/lib/bidi.ts` and `<Bidi>`.
- Layout and navigation by role.
- Login with the language switch visible before login, and "Continue as guest".
- Generated API types.

**Owns.** `frontend/src/{app,lib,styles}/`, `frontend/src/features/auth/`, `frontend/e2e/shell-*.spec.ts`.

**Acceptance**
- A language switch makes no `/api/*` request.
- The layout mirrors, with a screenshot pair.
- The bidi fixture renders correctly.

### F2 · Ask screen
**Scope.**
- Question box (Enter submits) and streaming answer.
- The three outcome states with the approved D4 copy. The refusal shows up to 3 "you may want to check" titles.
- Citation cards (title, page, snippet) that open the viewer, and the history side panel.
- **Never looks frozen:**
  - The stage is shown in words (queued at position P → searching → reading N sources → writing).
  - While waiting for the first token, elapsed time is shown against the estimate as a progress bar, with numbers through `useFormat()`.
  - The "may take about S seconds" notice appears when S > `ETA_NOTICE_SECONDS` (20).
  - "Still working, this is taking longer than usual" appears at 1.25 × the estimate.
  - In the low-confidence band, the amber banner shows from the `reading` event, before any token.
  - When `final.outcome = no_answer`, the streamed text is **replaced** by the refusal message.
- **Converted-file note.** A citation with `is_converted` says that the page refers to the converted PDF and may differ from Word.

**Owns.** `frontend/src/features/ask/`, `frontend/e2e/ask-*.spec.ts`. It works against a `page.route` mock of `/api/ask/stream` until R1 merges.

**Acceptance (Playwright with a slow mocked stream)**
- Stage text appears within 1 s.
- With S ≤ 20 no notice appears; with S > 20 the notice appears before `writing`; the overrun message appears.
- The amber banner appears before the first token.
- Streamed text is replaced when the outcome is `no_answer`.
- A DOCX citation shows the converted note in both locales, and a PDF citation doesn't.

### F3 · Library and Upload
**Scope.**
- **Library:** one row per version group, the current version.
  - Columns: title, file type, category, year, programme, uploaded by, date, page count, status.
  - A label such as **"v3 — current"** and "2 earlier versions".
  - Filters, search and paging. Row click opens the viewer.
  - Archive, retry and "upload new version" actions.
- **Upload:** drag and drop, multiple files, 3 at a time, per-file stage chips, and the failure reason translated from `error_code`.

**Owns.** `frontend/src/features/{library,upload}/`, `frontend/e2e/library-*.spec.ts`, `frontend/e2e/upload-*.spec.ts`.

**Acceptance**
- A seed document with 3 versions shows one row, "v3 — current" and "2 earlier versions", localised with digits through `useFormat()`.
- Uploading the `seed/bad` fixtures shows a readable reason for each.

### F4 · Document viewer
**Scope.**
- A pdf.js viewer that opens at `?page=N` and highlights the chunk span (S4 method), falling back to the whole page.
- The document page lists earlier versions and linked amendments, each with date and uploader, and each openable. A past citation to v1 opens v1.
- **Highlight-rate script (deliverable 5).**
  - Synthetic: the targets are the expected citations of the headline and dev questions.
  - Real reports: they have no questions, so the targets are every chunk span.
  - **Success** means at least 90% of the chunk's normalised characters match text-layer items on the right page. Anything else counts as a page-level fallback.
  - The real-report run uses the owner's separate samples stack, with a Playwright config that sets `trace`, `screenshot` and `video` to `off` and writes no HTML report. Test names are ids only, and the output is just `{set, total, matched, page_fallback}`.
- **The smoke test.**

**Owns.** `frontend/src/features/viewer/`, `frontend/e2e/viewer-*.spec.ts`, `frontend/e2e/highlight-rate.spec.ts`, `frontend/e2e/highlight-rate.config.ts`, `frontend/e2e/smoke.spec.ts`.

**Acceptance**
- The smoke test passes.
- The version list works.
- On the synthetic corpus the highlight script prints `highlight: X/Y (Z%) matched, N fallback`, and that output is in the report.

### F5 · Admin
**Scope.**
- Users: list, create and edit (role, active, language).
- Usage log table (user, question, outcome, time) with filters.
- **Outcome summary** for a chosen period:
  - all four outcomes as counts and percentages
  - refusals split into "no matching documents" (gate) and "model found no answer" (sentinel or no valid citation)
  - a trend per day or week
  - the most-refused questions with their median top score
- **Hosted-provider banner.** If `/health` reports a hosted `llm_provider`, a red banner says that questions and up to K excerpts are sent to that provider.

**Owns.** `frontend/src/features/admin/`, `frontend/e2e/admin-*.spec.ts`.

**Acceptance**
- With fixture queries, the summary matches `/admin/usage/summary` for a chosen period in both locales, and changing the period changes the numbers.
- The banner appears only in hosted mode.

---

## Evaluation

### E1 · Eval runner
**Scope.**
- `python -m sanad.eval` per SYSTEM_DESIGN §11. It runs on the **seed corpus only** and never reads `data/client-samples/`.
- Scoring, recall@K diagnostics, and Markdown and JSON reports with a per-question table.
- Failure categories: retrieval / generation / refusal / **page-split**. The page-split category is in the week-4 first run.
- `--provider` and `--model` select the model, so scores can be compared between the production model and the CPU demo model.
- `--repeat N` gives the mean and range for hosted runs.
- Every result records the provider, model ID, Ollama version and date, because free hosted models and their limits change often.
- **Hosted-reference guard.** A hosted-reference run needs egress, so it runs only in a stack started with the api-llm override whose database holds seed documents only. The runner checks this before the first call.

**Owns.** `backend/sanad/eval/`, `backend/tests/eval/`.

**Verify.** `docker compose run --rm backend-dev python -m sanad.eval --set test` prints `Score: X/25` and writes `eval/results/*.md`.

### E2 · Tuning
**Scope.**
- **Dev set only:**
  - the chunk sweep (D1)
  - threshold tuning (D4)
  - lexical `simple` vs `arabic`, and `strip_clitics`
- Write the tuned defaults into config and `.env.example`.
- **Headline runs** happen exactly once per reported configuration, on the **release candidate frozen for the week-8 demo**: the production model, the CPU demo model if it differs, and the free hosted reference model.
  - If code that affects answers changes after a headline run, the headline is re-run and both numbers are reported, with the reason.

**Owns.** `eval/results/`, and the default values of `T_REFUSE`, `T_CONFIDENT`, `CHUNK_TARGET_TOKENS` and `CHUNK_OVERLAP_TOKENS`. The manager copies the tables into DECISIONS.md.

**Acceptance**
- One table states the production score, the CPU demo score and the gap (deliverable 7).
- DECISIONS has no *est.* left for anything measured.

---

## Hardening and delivery

### H1 · Bulk upload resilience
**Scope.** A Playwright test uploads 50 files (45 good plus the 5 `seed/bad` fixtures). Every good file reaches `ready`, every bad one shows a readable reason, and the batch never stalls.

**Owns.** `frontend/e2e/bulk-upload.spec.ts`.

### H2 · Clean-machine and egress test
**Scope.**
- Fresh clone, then `docker compose -p sanad-cleantest up`, and `docker compose -p sanad-cleantest down -v` afterwards.
- Time the run until the seed corpus is ready and the guest gets an answer.
- No egress from `api`, `worker`, `ml`, `db` or `ollama` with the base compose file.
- If the first boot takes more than about 5 minutes, ship a pre-computed seed index.

**Owns.** `scripts/cleantest.sh`.

### H3 · README and acceptance run
**Scope.**
- README sections:
  - quick start for the IT person
  - stack justification
  - chunking rationale
  - **Decisions**, from DECISIONS.md without its editorial notes, containing verbatim *"Cost is not the reason to stay local; privacy is."*
  - eval results, including the questions that fail and why
  - configuration reference, including the hosted-provider banner
  - backup and restore
  - "Enabling the GPU" (from H4)
  - limitations: DOCX and TXT pages refer to the converted PDF, and the measured page-split rate
- **"Can documents leave the server?"** is one plain paragraph stating three things:
  - the containers that touch content have no internet route
  - an API-mode override exists in the code for benchmarking on synthetic data, and it is **not enabled**
  - how to check: `docker compose config` loads no `docker-compose.api-llm.yml`, plus the H2 egress command
- Run the brief's §12 acceptance checklist and record the evidence for each item.

**Owns.** `README.md`.

**Verify.** `grep -F 'Cost is not the reason to stay local; privacy is.' README.md && grep -F 'Can documents leave the server?' README.md`

### H4 · Production install and GPU cutover (before 31 Jan)
**Scope.**
- **`docker-compose.gpu.yml`:** NVIDIA reservations for `ollama` and `ml`.
- **"Enabling the GPU"** steps: host NVIDIA driver plus NVIDIA Container Toolkit, checked with `nvidia-smi` inside `ollama`.
- **Bulk import CLI:** `python -m sanad.ingest.bulk_import <dir> --uploaded-by <admin-email>`.
  - Same checks as `POST /documents`.
  - Resumable and idempotent.
  - Prints counts only.
- **Runbook** `docs/runbooks/install.md` for installing on the client server and running the first full archive ingestion.
  - The owner or the client's IT person runs it. Agents never see the archive.
  - It ends with `ingestion_summary`, which is deliverable 4.
- **Speed check:** the G1 harness on the synthetic corpus, on the client's card.

**Owns.** `docker-compose.gpu.yml`, `backend/sanad/ingest/bulk_import.py`, `backend/tests/ingest/test_bulk_import.py`, `docs/runbooks/install.md`.

**Acceptance**
- A bulk import of `seed/documents` plus `seed/bad` gives the same statuses and codes as HTTP upload, and a re-run changes nothing.
- p90 total time per answer ≤ 15 s on the client's card.
- The ingestion summary is delivered.

**Verify**
```
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d && docker compose exec ollama nvidia-smi
docker compose run --rm backend-dev pytest backend/tests/ingest/test_bulk_import.py -q
```
