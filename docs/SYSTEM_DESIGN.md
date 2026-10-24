# Sanad — System Design

Status: **v0.2**, 24 Oct 2026. Updated after the client accepted the decisions draft: never-frozen streaming, outcome summary, version history, client hardware, sample-report handling. Owner: project manager (Claude). Source of requirements: [brief.md](brief.md).
Decisions (accepted by the client on 24 Oct 2026) are in [DECISIONS.md](DECISIONS.md). Where a decision is more specific than the brief, the decision wins. Client questions: [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md). Work breakdown: [ROADMAP.md](ROADMAP.md).

Anything marked **(verify)** is a candidate that a spike must confirm before we build on it. It is not a settled fact.

> **Portfolio build scope (25 Oct 2026).** [BUILD_PLAN.md](BUILD_PLAN.md) is authoritative: Part 1 sets scope and schedule, and Part 2, the decisions log, sets behaviour. This design remains the reference, but these parts are **designed and deferred to v2**:
> - document versions, supersede and amendments (§4, §7)
> - paragraph-level highlighting: the build cites at **page level**
> - the Admin usage log, outcome summary and 12-month retention (§7)
> - everything GPU (§10)
> - hosted LLM providers: the adapters and override stay, and the build ships local only
>
> Changes from the plan:
> - a **`restricted`** document flag (§4, §9)
> - the client's six document categories (§4)
> - fallback locale **English**, with **Latin digits** in both languages (§8)
> - **15** headline eval questions (§11)
> - extraction with **pypdfium2**
> - the binding data-handling rule (§9)

---

## 1. Principles

These come straight from the brief. When two goals conflict, the one higher in the list wins.

1. **Never invent an answer.** A refusal is better than an answer the documents don't support. Every claim in an answer carries a citation, and an answer with no valid citation is treated as a refusal.
2. **No document content leaves the server.** That covers ingestion, embeddings, reranking, storage, generation and serving. The client has decided that API mode will never be used for their documents (DECISIONS D3). The API code path exists only for benchmarks on synthetic seed data, behind a deliberate override file and a code guard (§2, §9).
3. **Arabic first.** We treat RTL, normalisation and bidi as core requirements. They are not a later polish pass.
4. **Measured, not claimed.** Chunk size, model choice and refusal thresholds are all settled by the evaluation set.
5. **One command to run.** `docker compose up` on a clean machine, for an IT generalist.

---

## 2. Architecture

```mermaid
flowchart LR
  subgraph host["Client's server (docker compose)"]
    direction LR
    web["web<br/>nginx + React SPA<br/>:8080 (only exposed port)"]
    api["api<br/>FastAPI"]
    worker["worker<br/>ingestion pipeline"]
    ml["ml<br/>embeddings + reranker"]
    db[("db<br/>PostgreSQL + pgvector")]
    llm["ollama<br/>local LLM (default)"]
    files[("files volume<br/>/data/files")]
  end
  user(("Staff browser")) -->|HTTPS| web
  web -->|/api| api
  api --> db
  api --> ml
  api -->|LLM_PROVIDER=ollama| llm
  api -. "LLM_PROVIDER=openai_compat / anthropic<br/>synthetic benchmarks only, never client documents" .-> ext["External LLM API"]
  worker --> db
  worker --> ml
  worker --> files
  api --> files
```

### Services

| Service | Image / runtime | Role | Network |
|---|---|---|---|
| `web` | nginx (multi-arch) | Serves the built SPA and reverse-proxies `/api` to `api`. This is the only port that gets published. | `edge` + `backend` |
| `api` | Python 3.12, FastAPI, uvicorn | Auth, REST, the ask pipeline and LLM calls | `backend` (internal) |
| `worker` | Same image as `api`, runs `python -m sanad.worker` | Ingestion: extract, clean, chunk, embed and store. Also handles DOCX/TXT to PDF conversion through LibreOffice. | `backend` |
| `ml` | Python 3.12 with sentence-transformers or FlagEmbedding **(verify in S2)** | `/embed` and `/rerank`. Weights are baked in at build time and loaded offline at runtime. | `backend` |
| `db` | `pgvector/pgvector:pg16` | Relational data, vectors and full-text search | `backend` |
| `ollama` | `ollama/ollama` | Local generation. It receives every prompt, so it has **no internet route**. Weights are read from the `ollama_models` volume. | `backend` only |
| `init` | Same image as `api`, one-shot | Runs Alembic migrations, seeds users and programmes, and enqueues the seed documents | `backend` |
| `ollama-init` | `ollama/ollama`, one-shot (its own `ollama serve` + `ollama pull`) | Pulls `${OLLAMA_MODELS}` (the production model and the CPU demo model) into the shared `ollama_models` volume on first boot, then exits. It never sees a prompt. | `egress` only |

The `backend` network is declared `internal: true`, so `api`, `worker`, `ml`, `db` and `ollama` **cannot reach the internet**. Every container that touches document content is on that network. That is how we enforce principle 2 at the network level instead of trusting the code. The only container with internet access is `ollama-init`, which downloads weights and never handles content.

API mode is turned on with an override file, `docker-compose.api-llm.yml`, which attaches `api` to `egress`. It is used only for benchmarks on the synthetic seed corpus and is never deployed on a server that holds client documents. A code guard (§9) refuses hosted calls carrying any non-seed excerpt even if the override is applied by mistake.

Other compose overrides:
- `docker-compose.gpu.yml` adds NVIDIA device reservations to `ollama` and `ml`.
- `docker-compose.dev.yml` is **for development only** and relaxes isolation on purpose:
  - it adds bind mounts and hot reload
  - it attaches `api` to a non-internal network so it can reach a host-native Ollama through `OLLAMA_BASE_URL=http://host.docker.internal:11434`. Docker on macOS has no GPU access, so containerised inference there is CPU-only.

  The no-egress guarantee and its tests apply to the base `docker-compose.yml` only.

**Platforms.** Every image must build and run on `linux/amd64`, which the client server probably uses, and on `linux/arm64`, which our development Macs use. M0 checks this.

### Why this stack (short form; the README carries the long form)

- **Python and FastAPI.** Python has the strongest ecosystem for PDF extraction, embedding models and Arabic NLP. FastAPI generates an OpenAPI spec, and the frontend's TypeScript types are generated from that spec.
- **PostgreSQL with pgvector.** One datastore handles relational data, vectors (HNSW) and lexical search (`tsvector`). The IT person runs one database, and we get one backup story and transactional consistency between documents and chunks.
- **A Postgres-backed job queue** (`FOR UPDATE SKIP LOCKED`) instead of Celery and Redis. Document status already lives in the `documents` row, and leaving out a broker removes a moving part. At NGO scale (thousands of documents) this is plenty.
- **React, TypeScript and Vite** for the SPA, with TanStack Query for the data cache. The cache survives a language switch, which satisfies "switch language without reloading data". i18next handles translation.
- **Radix UI primitives and CSS Modules** instead of a styled component kit. We own every line of CSS, so a stylelint rule can enforce logical properties with no exceptions. Radix's `DirectionProvider` handles RTL for menus and popovers.
- **pdf.js** (`pdfjs-dist`) renders the viewer, with a text-layer highlight on the cited span.
- **LibreOffice (headless)** converts DOCX and TXT to PDF, so every document has real pages and one viewer path (§5.2).

---

## 3. Repository layout

```
backend/                  Python package `sanad` (api + worker share it)
  sanad/core/             config (pydantic-settings), db session, security, error codes
  sanad/api/              routers: auth, me, ask, queries, documents, programmes, admin, health
  sanad/text/arabic.py    THE normalisation library (single source of truth)
  sanad/ingest/           extract/, clean.py, chunk.py, pipeline.py, worker.py
  sanad/retrieval/        dense.py, lexical.py, fuse.py, rerank.py, gate.py
  sanad/llm/              base.py, ollama.py, anthropic.py, openai_compat.py, prompts/
  sanad/eval/             runner.py, scoring.py, validate.py
  alembic/  tests/  pyproject.toml  Dockerfile
ml/                       embedding + rerank service (own Dockerfile, weights baked at build)
frontend/
  src/locales/ar.json     ALL Arabic UI text
  src/locales/en.json     ALL English UI text
  src/app/ src/features/{auth,ask,library,upload,viewer,admin}/ src/lib/ src/styles/
deploy/nginx.conf
seed/                     manifest.json, documents/, sources/ (authoring sources), bad/ (failure fixtures)
eval/                     questions.yaml (25, headline), dev_questions.yaml (tuning), results/
docs/                     brief, design, decisions, roadmap, spikes/
docker-compose.yml  docker-compose.{api-llm,gpu,dev}.yml  .env.example  Makefile
```

---

## 4. Data model

The brief requires the fields marked ★. The others are design additions, with the reason given.

```sql
-- enums
user_role      : viewer | editor | admin
ui_lang        : ar | en
file_type      : pdf | docx | txt
doc_category   : annual_report | donor_agreement | programme_evaluation | field_survey | budget | board_minutes   -- no "other": NULL = uncategorised, flagged for review (client Q5)
doc_status     : queued | extracting | indexing | ready | failed
doc_language   : ar | en | mixed
answer_outcome : answered | low_confidence | no_answer | error

users (
  id uuid pk,
  name text ★, email citext unique ★, password_hash text ★ /* argon2id */,
  role user_role ★, preferred_language ui_lang ★,
  is_active bool default true,
  is_guest  bool default false,            -- guest is restricted to seed docs (§9)
  created_at, updated_at, last_login_at timestamptz
)

sessions (                                  -- opaque, revocable sessions (deactivating a user logs them out)
  id text pk /* sha256 of cookie token */, user_id fk, created_at, expires_at, last_seen_at
)

programmes (                                -- programme is an entity so it can have bilingual names + clean filters
  id uuid pk, code text unique, name_ar text, name_en text, is_active bool
)

documents (
  id uuid pk,
  title text ★, original_filename text ★, file_path text ★,
  viewer_path text,                         -- PDF rendition shown in the viewer (= file_path for PDFs)
  file_type file_type ★,                    -- brief's "type", reading 1
  category doc_category,                    -- brief's "type", reading 2 (OPEN_QUESTIONS Q5)
  year smallint ★, programme_id fk null ★,
  uploaded_by fk users ★, uploaded_at timestamptz ★,
  page_count int ★, status doc_status ★, language doc_language ★,
  error_code text, error_params jsonb,      -- readable failure, translated client-side; never a stack trace
  attempts int default 0, processing_started_at, ready_at timestamptz,
  sha256 char(64), size_bytes bigint,       -- duplicate detection
  tags text[] default '{}',
  is_archived bool default false, archived_at, archived_by,
  restricted bool default false,            -- client Q2: Editors/Admins only; excluded from RETRIEVAL for Viewers and guest
  version_group_id uuid, version int default 1, superseded_by uuid null,  -- DECISIONS D5
  amends_document_id uuid null, amendment_no smallint null,  -- D5/N3: amendment letter linked to its agreement; both stay in retrieval
  is_seed bool default false,
  title_norm text                           -- normalised title for library search
)

document_pages (                            -- kept so we can re-chunk without re-extracting, and highlight exact spans
  document_id fk, page_number int /* 1-based, = page in viewer_path */,
  text text, text_norm text, char_count int,
  primary key (document_id, page_number)
)

chunks (
  id uuid pk,
  document_id fk ★, page_number int ★, chunk_index int ★,
  text text ★,                              -- display text (cleaned, not normalised)
  text_norm text,                           -- normalised for lexical match
  char_start int, char_end int,             -- span inside document_pages.text → paragraph-level highlight (D6)
  token_count int,
  embedding vector(1024) ★,                 -- dimension follows the chosen model (verify in S2)
  embedding_model text,                     -- detects stale vectors after a model change
  index_generation int,                     -- re-indexing writes a new generation; retrieval uses the active one
  tsv tsvector generated always as (to_tsvector('simple', text_norm)) stored,
  unique (document_id, index_generation, chunk_index)
)
-- indexes: hnsw (embedding vector_cosine_ops); gin (tsv); btree (document_id, page_number)

queries (                                   -- also the admin usage log
  id uuid pk, user_id fk ★, question text ★, answer text ★ null, language ui_lang ★,
  outcome answer_outcome, top_score real, filters jsonb,
  refusal_reason text null,                 -- gate | sentinel | no_valid_citation (tells honesty apart from retrieval, D4)
  llm_provider text, llm_model text, latency_ms int, prompt_tokens int, completion_tokens int,
  created_at timestamptz ★
)

citations (
  id uuid pk, query_id fk ★, chunk_id fk ★, rank smallint ★ /* = the [n] marker */, score real,
  unique (query_id, rank)
)

audit_events (                              -- admin-visible: logins, uploads, archives, role changes
  id bigserial pk, actor_id fk, action text, target_type text, target_id uuid, meta jsonb, created_at
)

llm_perf_samples (                          -- measured speed on THIS machine → the "may take ~S seconds" estimate (§6)
  id bigserial pk, llm_model text, prompt_tokens int, prompt_ms int, output_tokens int, output_ms int, created_at
)
```

**Invariants**
- Documents and chunks are never hard-deleted in v1. Archiving or superseding a document only removes it from retrieval, so every historical citation still resolves.
- Chunks are immutable within an index generation.
  - Re-indexing (new chunk parameters or a new embedding model) writes a new generation and switches retrieval to it atomically.
  - It **never** creates a user-visible document version.
  - Old chunks are kept while any `citations` row points at them.
- `page_number` always refers to the page in `viewer_path`, so what we cite is what the viewer shows.
- **Versions** (D5):
  - `version_count` is the number of versions in the group, including the current one, so the Library shows `version_count − 1` earlier versions.
  - `is_current` means `superseded_by IS NULL`.
  - The previous version stays current until the new one is `ready`, and a failed new version never supersedes.
  - Archiving the current version does not make an older version current.
- **Amendments** (`amends_document_id` set) never supersede anything. Both the agreement and its amendment letters stay in retrieval (N3).

---

## 5. Flow: upload to ready

### 5.1 Stages

| UI label | Where | `documents.status` |
|---|---|---|
| Uploading (n%) | browser XHR progress | — (row doesn't exist yet) |
| Uploaded | `POST /api/documents` committed | `queued` |
| Extracting | worker | `extracting` |
| Indexing | worker (chunk + embed + store) | `indexing` |
| Ready | worker | `ready` |
| Failed + reason | any stage | `failed` + `error_code` + `error_params` |

**Bulk upload.** The browser uploads files one request each, three at a time. Each file is independent, so one corrupt file fails only its own row and the rest of the batch carries on (acceptance criterion: 50 files with one corrupt). The Upload screen polls `GET /api/documents?ids=…` every 1.5 s until every file reaches a terminal state.

### 5.2 Pipeline (worker)

1. **Claim.** `UPDATE documents SET status='extracting', attempts=attempts+1 … WHERE id = (SELECT id FROM documents WHERE status='queued' ORDER BY uploaded_at FOR UPDATE SKIP LOCKED LIMIT 1)`. On startup the worker re-queues stale `extracting`/`indexing` rows (`attempts < 3`) and fails the rest with `WORKER_TIMEOUT`.
2. **Normalise to PDF.**
   - PDF: used as-is.
   - DOCX and TXT: LibreOffice headless converts them to PDF, with Arabic fonts installed (Noto Naskh/Sans Arabic, Amiri, KACST; **verify** in S4).
   - TXT encoding: the worker decodes the file itself (UTF-8, then UTF-8-BOM, then Windows-1256, which is common for Arabic Windows exports) and hands LibreOffice **UTF-8**. C1b found that LibreOffice does not detect Windows-1256 and produces mojibake. LibreOffice does honour form feeds (`\f`) as page breaks.
   - DOCX has no fixed pagination, so the PDF rendition *defines* its page numbers. They can differ slightly from Word's on-screen paging, and the README states this.
3. **Extract** per-page text from the PDF with the library chosen in spike S1. Candidates: `pypdfium2`, `PyMuPDF`, `pdfminer.six` **(verify licence and Arabic quality)**.
4. **Clean** with `sanad.text.arabic.clean_extracted`:
   - NFKC normalisation, which folds Arabic presentation forms (U+FB50–U+FEFF) back to base letters
   - repair of visual-order (reversed) lines, using heuristics from S1
   - removal of bidi control characters
   - whitespace collapsing
   - removal of running headers and footers (lines that repeat on more than 50% of pages)
5. **Validate.** Detect each failure below and fail with its code.

   | Code | Meaning |
   |---|---|
   | `FILE_CORRUPT` | The file can't be parsed |
   | `PDF_ENCRYPTED` | Password-protected PDF |
   | `NO_TEXT_LAYER` | Fewer than N characters per page on more than X% of pages, i.e. a scan. OCR is out of scope, so we say so plainly. |
   | `EMPTY_DOCUMENT` | No usable text |
   | `UNSUPPORTED_TYPE` | Not PDF, DOCX or TXT |
   | `FILE_TOO_LARGE` | Over the size limit |
   | `CONVERSION_FAILED` | LibreOffice couldn't convert the file |
   | `TXT_ENCODING_UNKNOWN` | None of the encodings decoded the file |

6. **Detect language** (`ar`/`en`/`mixed`) from the share of Arabic letters, and store `document_pages`.
7. **Chunk** each page. Chunks are paragraph-aware, sized by the embedding model's tokenizer, and never cross a page boundary (DECISIONS D1). Store `char_start` and `char_end`.
8. **Embed** in batches through `ml /embed`, with status `indexing`.
9. **Store** chunks in one transaction, set `status='ready'`, and set `superseded_by` on the previous version if this upload is a new version (D5).

Errors raise `IngestionError(code, params)`. Unexpected exceptions become `INTERNAL_ERROR` with a log reference id, and the stack trace goes **only** to server logs.

Duplicates are caught at upload time: an identical `sha256` that already exists as a non-archived document returns `409 DUPLICATE_DOCUMENT` with the existing id.

---

## 6. Flow: question to answer

```mermaid
sequenceDiagram
  participant U as Browser
  participant A as api
  participant M as ml
  participant D as db
  participant L as LLM
  U->>A: POST /api/ask {question, filters}
  A->>A: normalise + detect language
  A->>M: embed(question)
  A->>D: dense top-40 (pgvector) ∥ lexical top-40 (tsvector on text_norm)
  A->>A: reciprocal-rank fusion → top-30
  A->>M: rerank(question, 30 chunks) → scores 0..1
  alt top score < T_refuse
    A->>D: store query (outcome=no_answer), no LLM call
    A-->>U: {outcome: no_answer, nearest_documents}
  else
    A->>L: system prompt + top-K excerpts labelled [1]..[K] + question
    L-->>A: answer with [n] markers (or NO_ANSWER sentinel)
    A->>A: validate markers → citations (no valid marker ⇒ no_answer)
    A->>D: store query + citations
    A-->>U: {outcome: answered | low_confidence, answer, citations[]}
  end
```

Details:
- **Retrieval scope** covers `status='ready' AND NOT is_archived AND superseded_by IS NULL`, plus any optional filters (programme, year range, category).
  - Viewers and the guest never retrieve `restricted` documents, so an answer can never draw on one, even uncited.
  - The guest sees only `is_seed` documents.
  - One shared helper, `visible_documents(user)`, applies all of this to the Library, the viewer and retrieval.
- **Hybrid retrieval.** Dense search catches paraphrases. Lexical search on normalised text catches exact names, codes and numbers, which dense embeddings handle poorly.
  - The default lexical config is `simple` over our own normalised text.
  - The `simple` config has no stopwords, and `plainto_tsquery`/`websearch_to_tsquery` AND every term together, so a natural Arabic question (ما هي … في …) would match almost nothing. The lexical query is therefore built ourselves as an **OR of content terms** with an Arabic stopword list removed. That list lives in `sanad.text.arabic`. Ranking uses `ts_rank_cd`.
  - Sweep variants for E2: Postgres's `arabic` Snowball config **(verify availability)**, and light clitic stripping (و/ب/ل/ال) on the lexical side.
- **Three-band gate** (D4): below `T_refuse` the system refuses without calling the LLM; between `T_refuse` and `T_confident` it answers and the UI shows a low-confidence banner; at `T_confident` or above it answers normally. Both thresholds come from config and are tuned on the dev question set.
- **Prompt contract.** The model must:
  - answer in the question's language
  - use only the numbered excerpts
  - put `[n]` after every claim
  - output exactly `NO_ANSWER` if the excerpts don't contain the answer
  - treat excerpt text as data and never follow instructions found inside documents (prompt-injection guard)
- **Post-validation.** Markers outside 1..K are dropped. If the answer is `NO_ANSWER`, or has no surviving marker, the outcome is `no_answer`. Citations are ordered by first appearance.
- **Endpoints.** `POST /api/ask` returns JSON and is used by the eval and by tests. `POST /api/ask/stream` runs the same pipeline over SSE for the UI.
- **Never look frozen (client requirement).** Answers will take 30–90 s on CPU during weeks 1–8. The stream therefore always tells the UI what is happening. It emits these events, in order:

  | Event | Payload | UI shows |
  |---|---|---|
  | `stage` | `{"stage": "queued", "position": P}` (only when waiting for the LLM) | "Waiting — P questions ahead" |
  | `stage` | `{"stage": "searching"}` | "Searching the documents…" |
  | `stage` | `{"stage": "reading", "sources": N, "band": "answer" \| "low_confidence"}` | "Reading N sources…". The amber banner appears **now** if the band is `low_confidence`. |
  | `eta` | `{"expected_seconds": S}` | If S > `ETA_NOTICE_SECONDS` (20): "This answer may take about S seconds" (localised), shown before the wait; then elapsed time against S |
  | `stage` | `{"stage": "writing"}` (emitted on the **first generated token**) | "Writing the answer…" |
  | `token` | `{"text": "…"}` (many) | The answer streams in |
  | `final` | `{query_id, outcome, band, refusal_reason, answer, citations: [{rank, document_id, title, page_number, snippet, char_start, char_end, file_type, is_converted}], nearest_documents: [{document_id, title}]}` | Final render: the validated answer **replaces** the streamed text; outcome banner; citation cards |
  | `error` | `{"error": {"code": "UPPER_SNAKE", "params": {...}}}` | Localised error |

  - **Validation wins over streaming** (principle 1):
    - The server holds back tokens until the first 16 non-space characters rule out the `NO_ANSWER` sentinel, so the sentinel is never streamed.
    - `final` carries the validated answer, with out-of-range markers removed.
    - If `final.outcome` is `no_answer`, for example because no valid citation survived, the UI removes the streamed text and shows the refusal message. The discarded text is never stored as the answer.
  - A refusal below `T_refuse` goes straight from `reading` to `final`, with no `writing`.
  - Prompt processing on CPU produces no tokens, so the stage stays `reading` while the UI shows elapsed time against `expected_seconds`. Past 1.25 × the estimate it says "still working, taking longer than usual".
  - `expected_seconds` uses the rolling prompt-processing and generation speeds of this machine (`llm_perf_samples`, updated after every answer), applied to the actual prompt size. It also adds the estimated time of requests ahead in the queue. Before any samples exist it uses `ETA_DEFAULT_SECONDS`.
  - **Queueing.** Generation runs under `LLM_MAX_CONCURRENCY`, which defaults to 1 on CPU. Waiting requests get `queued` events.
  - **Transport.** The SSE response sets `Content-Type: text/event-stream`, `Cache-Control: no-cache` and `X-Accel-Buffering: no` (`deploy/nginx.conf` relies on it), and sends `: ping` every 15 s while no other event is due.
  - Stage labels are UI text: the server sends only stage codes.
- **Refusal reason.** `gate` (retrieval below `T_refuse`), `sentinel` (the model said `NO_ANSWER`) or `no_valid_citation`. It's stored on `queries`, so the Admin summary can separate "the documents don't cover this" from "the model found nothing usable".
- **Refusal text is UI text.** The server returns `outcome: no_answer` with no prose, and the client shows the localised message from `ar.json`/`en.json`.

---

## 7. API surface (v1)

All routes are under `/api`. Errors always take the form `{"error": {"code": "SOME_CODE", "params": {...}}}`, and the client translates the code. FastAPI's OpenAPI spec is the contract, and `make gen-api-types` regenerates `frontend/src/api/schema.d.ts`.

| Method & path | Role | Purpose |
|---|---|---|
| `POST /auth/login` · `POST /auth/logout` · `POST /auth/guest` | public | Session cookie (httpOnly, SameSite=Lax). Login attempts are rate-limited. |
| `GET /me` · `PATCH /me` | any | Profile. Language preference. |
| `POST /ask` · `POST /ask/stream` | viewer+ | Ask (§6) |
| `GET /queries` · `GET /queries/{id}` | viewer+ (own) | History side panel |
| `GET /documents` | viewer+ | Library: `q, file_type, category, year_from, year_to, programme_id, status, include_archived, include_superseded` (default false, so one row per version group), `sort, page`. Every item carries `version`, `is_current` and `version_count`. |
| `GET /documents/{id}` · `GET /documents/{id}/file` · `GET /documents/{id}/pages/{n}` | viewer+ | Metadata (same version fields), the PDF rendition (streamed, auth-checked), and page text with spans |
| `GET /documents/{id}/versions` | viewer+ | Every version in the group plus linked amendments, each with `kind: version \| amendment`, date and uploader (client addition to D5) |
| `POST /documents` (multipart, 1 file) · `PATCH /documents/{id}` | editor+ | Upload, with optional `replaces_document_id` (new version) **or** `amends_document_id` (linked amendment, never supersedes); edit metadata and tags |
| `POST /documents/{id}/archive` · `/unarchive` · `/retry` | editor+ | Lifecycle |
| `GET /programmes` | viewer+ | Filter options (bilingual names) |
| `GET/POST/PATCH /admin/users` | admin | User management (no hard delete; deactivate) |
| `GET /admin/usage` | admin | Who asked what and when (queries ⨝ users), with filters, plus `audit_events` |
| `GET /admin/usage/summary?from&to&bucket=day\|week` | admin | Counts and percentages of refused / low confidence / answered / error, as shares of all questions in the period, per bucket for the trend. Refusals are split by `refusal_reason`. The most-refused questions are grouped by `normalize_for_search(question)`, with count and median `top_score` (client addition to D4). |
| `GET /health` | public | db, ml and llm reachability (no details beyond up/down), plus `llm_provider`, so the Admin screen can warn if a hosted provider is configured |

---

## 8. Frontend: i18n, RTL and bidi

- **Strings.** All UI text lives in `frontend/src/locales/ar.json` and `en.json` and is reached through `t()`. ESLint `i18next/no-literal-string` runs as an **error** (JSX text plus `placeholder`, `title`, `aria-label` and `alt` attributes). A unit test checks that both files have identical key sets, and that every backend error code has a translation in both.
- **Direction.** On boot and on every `languageChanged` event we set `document.documentElement.lang` and `dir`, the latter from `i18n.dir()`. Radix `DirectionProvider` receives the same value.
- **CSS.** Logical properties only: `margin-inline-start`, `padding-block`, `inset-inline-end`, `text-align: start`. Stylelint (`stylelint-use-logical` or equivalent, **verify**) rejects physical properties. Directional icons such as arrows and chevrons mirror with a `[dir=rtl]` transform.
- **Language entry.** `?lang=ar` and `?lang=en` set the locale on any route, before or after login. Priority order: URL, then the logged-in user's preference, then the last choice in localStorage, then **`en`**. The demo opens in English, and the guest link is `?lang=en`. Switching language while logged in sends `PATCH /me`. Only `i18n` state changes, so no data refetch happens.
- **Formatting.** A `useFormat()` hook wraps `Intl.DateTimeFormat`, `NumberFormat` and `RelativeTimeFormat` for the active locale. Digits are **Latin (123) by default in both languages** (client Q6), via `-u-nu-latn`. Arabic-Indic digits are a config switch (`AR_NUMBERING=arab`). Hand-built date or number strings are not allowed.
- **Mixed content.** Every content block (answers, snippets, titles, filenames) renders with `dir="auto"` and `unicode-bidi: plaintext`. Inside answers, Latin runs, codes and URLs are wrapped in `<bdi>` by `src/lib/bidi.ts`. The regression fixture is `"تم تمويل المشروع YEP-2021-03 عبر https://example.org/r في ٢٠٢١"`.
- **Fonts.** Self-hosted through `@fontsource` (an Arabic face such as IBM Plex Sans Arabic or Noto Sans Arabic, plus a Latin face). No CDN.
- **Three-clicks path.** Login lands on Ask, Enter submits, and clicking a citation card opens the viewer at that page with the span highlighted. The login page also has a "Continue as guest" button.

---

## 9. Security and privacy

| Concern | Design |
|---|---|
| Content egress | Every content-handling container (`api`, `worker`, `ml`, `db`, `ollama`) is on the `internal: true` network only. Model weights are fetched at build time (`ml`) or by the content-free `ollama-init` job. `HF_HUB_OFFLINE=1`. No CDN assets. No telemetry. |
| API-mode LLM | **The client decided it will not be used for their documents.** The code path stays for benchmarking on synthetic data. Turning it on needs the override file **and** `LLM_PROVIDER`. **Code guard:** hosted providers (`openai_compat`, `anthropic`) make no call, returning `HOSTED_LLM_NON_SEED_DATA`, if any excerpt comes from a document with `is_seed = false`. If a hosted provider is configured, `/health` reports it, the Admin screen shows a red banner ("questions and up to K excerpts are sent to <provider>"), and the README says the same. |
| Data-handling rule (binding, client) | "No content from the Foundation's archive is ever sent to any external service, including AI coding assistants, under any circumstances, **including debugging**. Diagnosis uses file names, error messages, page counts and extracted statistics only. If a document must be examined, it is examined on the Foundation's own server." This rule goes in the README. **Exception:** the eight sample reports are already public and may be handled normally. Keep them in `data/client-samples/` (git-ignored); they are not ours to republish. |
| Guest | `is_guest` viewer with `GUEST_MODE=seed_only` (default): sees only `is_seed` documents in the library, retrieval and viewer. `GUEST_MODE=off` disables the guest entirely. |
| Document access | A `restricted` flag (client Q2) makes a document visible to Editors and Admins only. It is excluded from the Library, the viewer (404) **and retrieval** for Viewers and the guest. Everything else is readable by every signed-in user. |
| Passwords and sessions | argon2id; opaque session tokens stored hashed; idle and absolute expiry; deactivation revokes sessions. |
| CSRF | SameSite=Lax cookie, and state-changing routes require `Content-Type: application/json` or multipart plus a custom `X-Sanad` header. |
| Uploads | Size limit, type checked by magic bytes as well as extension, files stored under generated paths and never by user filename, and the file served only through the auth-checked endpoint. |
| Logs | App logs never contain chunk or page text. The `queries` table *is* the usage log, and its retention is configurable (Q7). |
| Prompt injection from documents | Excerpts are delimited and the system prompt says to ignore instructions found inside them. Answers are rendered as text, never HTML. |

---

## 10. Models and where they live

| Component | Default candidate (verify) | Runs | Weights |
|---|---|---|---|
| Embeddings | `BAAI/bge-m3` (1024-d, multilingual, long context); alternates `multilingual-e5-large`, `gte-multilingual-base` | `ml` container, CPU (GPU optional) | Baked into the `ml` image at build |
| Reranker | `BAAI/bge-reranker-v2-m3` | `ml` | Baked into the `ml` image |
| Generation (local) | Pick from the S3 shoot-out: Qwen 7–14B instruct, Gemma 12B, ALLaM 7B, Command R7B Arabic (licence may be non-commercial; verify) | `ollama` | `ollama_models` volume, pulled once by `ollama-init` |
| Generation (hosted reference; synthetic data only) | A free hosted model through the generic `openai_compat` adapter (provider chosen by the manager, P3). The same adapter also serves vLLM or llama.cpp hosts. The `anthropic` adapter (official SDK; `claude-opus-5-5`, `claude-sonnet-5-5` or `claude-haiku-5-5`) is built and tested with fakes, is optional, and needs no key. | external | — |

Config (`.env`):
- LLM provider and models: `LLM_PROVIDER=ollama|openai_compat|anthropic`, `LLM_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_MODELS` (the production model and the CPU demo model)
- Hosted adapters: `OPENAI_COMPAT_BASE_URL`, `OPENAI_COMPAT_API_KEY` (optional), `ANTHROPIC_API_KEY` (optional)
- Retrieval and chunking: `RETRIEVAL_TOP_K`, `T_REFUSE`, `T_CONFIDENT`, `CHUNK_TARGET_TOKENS`, `CHUNK_OVERLAP_TOKENS`
- Streaming: `ETA_DEFAULT_SECONDS`, `ETA_NOTICE_SECONDS=20`, `LLM_MAX_CONCURRENCY`
- Access and display: `GUEST_MODE`, `AR_NUMBERING`

**First boot needs internet** to pull base images and the LLM weights (~5–10 GB depending on the models). After that the system runs offline. An air-gapped install path (`make bundle`, a tarball of images and weights) is a stretch goal with no task yet, listed as a follow-up of H2.

**Client hardware.**
- The server has 16 cores and 64 GB of RAM, with no GPU.
- A 24 GB GPU is approved in principle and must be installed before 31 January.
- Weeks 1–8 run on CPU, with 30–90 s answers accepted for the demos. Production needs under 15 s, which needs the GPU.
- The **production model** is chosen for the GPU. If the CPU demo model differs, the eval is run on both and the gap is reported.

**Memory budget** (estimates, verified in S2 and S3): db ~1 GB, ml ~3–5 GB, a 7–8B Q4 LLM ~6 GB (14B ~10 GB), worker plus LibreOffice ~1 GB. The client's 64 GB leaves ample headroom. On development Macs, set Docker Desktop's memory to at least 16 GB, or run Ollama natively on the host for Metal speed.

---

## 11. Evaluation harness

- `eval/questions.yaml` holds **15 headline** questions (BUILD_PLAN: reduced from 25). They are never used for tuning. IDs are stable, so the gaps in the numbering are intentional.
- `eval/dev_questions.yaml` holds 30 **tuning** questions, including the 10 former headline items (D21–D30), used for thresholds, so the headline number isn't overfit.
- Question mix in the 15:
  - 8 Arabic factual questions, including tatweel, diacritics, a code inside Arabic, and one page-split item
  - 2 cross-document questions
  - 2 English questions, one about an Arabic document
  - 3 **unanswerable** questions, 2 of them near-misses where a related document exists but doesn't contain the answer
- Answerable items carry `must_include` facts (normalised strings and numbers) and `expected_citations: [{file, page}]`. Unanswerable items carry `expected_outcome: no_answer`.
- **Scoring.** An answerable item is correct only if:
  - its outcome is `answered` or `low_confidence`, and
  - every `must_include` fact is present in the normalised answer (numbers are normalised across digit sets and separators), and
  - at least one expected `(file, page)` is among the citations.

  An unanswerable item is correct only if its outcome is `no_answer`.
- **Diagnostics.** We also report retrieval recall@K, meaning whether the expected page was in the candidates. That lets the README separate *retrieval* failures from *generation* failures for each failing question.
- **Run:** `docker compose run --rm backend-dev python -m sanad.eval [--set test|dev] [--provider ollama|openai_compat|anthropic] [--model NAME] [--repeat N]` writes `eval/results/<timestamp>.{json,md}` and prints `Score: X/15`.
  - `--set test` is the 15 headline questions; `--set dev` is the 30-question tuning set.
  - The eval runs on the seed corpus only.
  - A hosted-reference run needs egress. It runs only in a stack started with `docker-compose.api-llm.yml` whose database holds seed documents only, and the runner checks that before the first call.
- **Failure categories:** retrieval / generation / refusal / page-split. Page-split means the expected fact sits in a paragraph that crosses a page boundary.
- `python -m sanad.eval.validate` checks that every expected citation's `must_include` text actually appears on that page of the extracted text, so the eval stays consistent with itself.
