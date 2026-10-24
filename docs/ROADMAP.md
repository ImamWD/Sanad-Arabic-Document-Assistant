# Roadmap and executor task briefs

**How we work**
- The project manager (Claude, this session) plans, reviews and verifies. Executor Claude Code agents implement.
- Each task below is self-contained. An executor reads [`CLAUDE.md`](../CLAUDE.md), [`brief.md`](brief.md), [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md) and its own brief.
- Each executor works on branch `task/<ID>-<slug>` and finishes with a PR that lists what it verified.
- The manager re-runs the **Verify** commands, reviews the diff against the acceptance criteria, and merges only when they pass.
- No task is "done" on the executor's word alone.

## Tracks and order

```
              ┌─ S1 extraction ─┐
M0 ──────────►├─ S2 embeddings ─┼──► B3 ingestion ──► R1 ask ──► E1 eval ──► E2 tuning ──► H1–H3 hardening
 (foundation) ├─ S3 local LLM ──┤        ▲                ▲                        ▲
              ├─ S4 viewer ─────┘        │                │                        │
              ├─ B1 arabic lib ──► B2 schema/auth ────────┘                        │
              └─ F1 shell ──► F2 ask ─► F3 library/upload ─► F4 viewer ─► F5 admin ┘
C1a corpus + eval authoring (text only) ── day 1 ──► C1b render + check (after M0) ──► feeds S1–S4, E1
```

**Parallel-safe groups.** Writers never share files; ownership is listed per task.
- Wave 0, day 1: M0 and C1a run in parallel. C1a needs no code or containers.
- Wave 1, right after M0: C1b first (an early drop of about 8 documents plus the dev questions unblocks the spikes), then S1, S2, S3, S4, B1 and F1.
- Wave 2: B2, plus F2 against mocked API types.
- Wave 3: B3, R1, F3, F4, F5.
- Wave 4: E1 and E2.
- Wave 5: H1, H2, H3.

Throughout, *Verify* means the exact commands the manager will run. Executors must run them first and paste the output into the PR.

---

## M0 — Foundation (one executor, blocks everything except C1)

### M0 · Scaffold, compose skeleton, lint gates
**Scope.**
- Repository layout per SYSTEM_DESIGN §3.
- Compose services: `db`, `api` (health only), `worker` (idle loop), `ml` (stub `/health`), `web` (nginx + Vite build). Plus `.env.example` and a `Makefile` (`up`, `down`, `lint`, `test`, `fmt`, `gen-api-types`).
- `backend` network `internal: true`.
- Lint gates, wired from the first commit:
  - ruff + mypy (backend)
  - ESLint with `i18next/no-literal-string` set to **error**
  - stylelint rejecting physical properties (`margin-left`, `padding-right`, `left:`, `text-align: left`, …)
  - a test that `ar.json` and `en.json` have identical key sets
- Frontend: `ar.json` and `en.json` hold the app title and the language switch label. `dir` and `lang` are set on `<html>`. `?lang=` works.
- A `tools` compose profile with a Node container, so `make test-frontend` runs vitest and Playwright. Also a Chromium plus LibreOffice tool image for C1b rendering. Host Python and host Node are never required.
- A GitHub Actions workflow running `make lint test`.
- `.gitignore` covering `.DS_Store`, `.env`, model weights and `data/`.

**Owns.** Everything (first task).

**Acceptance**
- `docker compose up -d --build` succeeds on a clean checkout on arm64 (dev Mac). The `docker buildx build --platform linux/amd64` builds also succeed for `api` and `ml`.
- `curl -fsS localhost:8080/api/health` returns `{"status":"ok","db":"ok","ml":"ok"}`.
- `localhost:8080/?lang=ar` renders RTL with `<html dir="rtl" lang="ar">`, and `?lang=en` renders LTR.
- A probe file with a JSX literal string, and another with `margin-left`, each make `make lint` **fail**.
- With the base compose file only (no dev override), `docker compose exec api python -c "import urllib.request;urllib.request.urlopen('https://example.com',timeout=5)"` **fails** (no egress).

**Verify**
```
docker compose up -d --build && curl -fsS localhost:8080/api/health
make lint && make test
printf 'export const P = () => <p>Hello</p>;\n' > frontend/src/__probe.tsx; make lint; echo "exit=$?"; rm frontend/src/__probe.tsx
printf '.x{margin-left:4px}\n' > frontend/src/__probe.module.css; make lint; echo "exit=$?"; rm frontend/src/__probe.module.css
docker compose exec api python -c "import urllib.request;urllib.request.urlopen('https://example.com',timeout=5)"; echo "exit=$?"
```

---

## Spikes (time-boxed, each output is a report in `docs/spikes/Sx-*.md` plus a runnable script)

### S1 · Arabic PDF text extraction
**Scope.**
- Compare `pypdfium2`, `PyMuPDF` and `pdfminer.six` on (a) the C1 seed PDFs and (b) at least 5 real-world Arabic PDFs (OPEN_QUESTIONS P2/Q10).
- Measure:
  - correct logical order
  - presentation-form folding
  - the lam-alef ligature
  - Arabic-Indic digits
  - Latin codes and URLs inside Arabic sentences
  - tables
  - speed
  - licence
- Specify the visual-order detection and repair heuristic, and the `NO_TEXT_LAYER` thresholds.

**Owns.** `docs/spikes/S1-extraction.md`, `spikes/s1/`.

**Acceptance.** The report includes a per-PDF comparison table, a recommendation with its licence implications, and the cleaning rules as test cases that are ready to be added to B1.

**Verify.** `docker compose run --rm api python spikes/s1/compare.py seed/documents /path/to/real` reproduces the table.

### S2 · Embedding and reranker shoot-out
**Scope.**
- Compare `bge-m3`, `multilingual-e5-large` and `gte-multilingual-base`, and confirm `bge-reranker-v2-m3` as the reranker.
- Use a mini retrieval set of 20 question→page pairs from the C1 dev questions.
- Measure:
  - recall@5 and recall@10, dense alone versus with the reranker
  - CPU throughput in chunks per second (arm64 measured, x86 estimated)
  - memory use
  - licence
- Also try ONNX or int8 builds for CPU speed.

**Owns.** `docs/spikes/S2-embeddings.md`, `spikes/s2/`.

**Acceptance.** A recommendation backed by numbers, and the inputs for DECISIONS D2's cost table.

### S3 · Local LLM shoot-out
**Scope.**
- Candidates: about 4 models available in Ollama (a Qwen 7B and a 14B instruct, Gemma ~12B, ALLaM 7B or another Arabic-tuned model; check each licence).
- Run 10 fixed RAG prompts with Arabic excerpts from the seed corpus, 3 of them unanswerable.
- Score:
  - follows "answer only from excerpts"
  - emits `[n]` markers
  - emits `NO_ANSWER` when the answer isn't there
  - Arabic fluency (rubric)
  - prompt-processing and generation speed on CPU in a container, with host-Metal speed for reference
  - RAM
- Optionally run a Claude baseline on the same synthetic prompts if a key is provided (P3).

**Owns.** `docs/spikes/S3-local-llm.md`, `spikes/s3/`.

**Acceptance.** A ranked table and a recommended default model, plus the inputs for D3's hardware table.

### S4 · Viewer highlight and DOCX fidelity
**Scope.**
- Build a pdf.js prototype that opens page N and highlights a given text span by matching normalised text against the text layer.
- Measure the success rate on seed and real Arabic PDFs.
- Convert 3 Arabic DOCX files through LibreOffice headless inside the worker image, choose fonts, and check that shaping is correct in the output.

**Owns.** `docs/spikes/S4-viewer.md`, `spikes/s4/`.

**Acceptance.** The highlight success rate, the failure modes, and the font package list to put in the worker Dockerfile.

---

## C1 · Seed corpus and evaluation set (content track)

This task is split by dependency:
- **C1a starts on day 1.** It is pure authoring, with no containers: `seed/sources/*`, `seed/manifest.json`, `eval/questions.yaml` and `eval/dev_questions.yaml`.
- **C1b runs after M0.** It renders the sources to PDF, DOCX and TXT using the M0 tools image, builds `seed/bad/`, and writes and runs the checker.
- **Early drop.** About 8 documents plus the dev questions are delivered first, because S1, S2 and S4 need them.

**Scope.**
- **Programmes.** 6 fictional programmes with realistic bilingual names. Suggested:
  - برنامج تمكين الشباب للتوظيف
  - مشروع المياه والإصحاح البيئي في المناطق الريفية
  - برنامج دعم التعليم الأساسي للفتيات
  - برنامج سُبل العيش للنساء المعيلات
  - برنامج الصحة المجتمعية
  - مبادرة الحماية الاجتماعية والدعم النقدي
- **Documents.** About 30, spanning 2015–2025:
  - categories: annual reports, donor agreements, evaluations, surveys, budgets, board minutes
  - languages: ~80% Arabic, ~15% English, a few mixed
  - formats: ~24 PDF, 4 DOCX, 2 TXT (one in Windows-1256)
  - length: 3–20 pages each
  - content must include numeric tables, project codes and URLs inside Arabic sentences, and some diacritics or tatweel in the source text
  - all personal data must be **obviously synthetic**
- **Authoring pipeline.** Write content in `seed/sources/*.md|html`, then render to PDF with a **real shaping engine** (Chromium via Playwright, or LibreOffice). Never use a naive PDF library. Commit both the sources and the rendered files, plus `seed/manifest.json` (title_ar/title_en, category, year, programme, language, file).
- **Failure fixtures** in `seed/bad/`:
  - a truncated (corrupt) PDF
  - a password-protected PDF
  - an image-only (scanned) PDF
  - an empty DOCX
  - a `.exe` renamed to `.pdf`
- **Eval sets.**
  - `eval/questions.yaml` holds the 25 headline questions, using the mix in SYSTEM_DESIGN §11.
  - `eval/dev_questions.yaml` holds about 15 tuning questions, none of them duplicating headline questions.
  - Each answerable item has `must_include` facts and `expected_citations`.
- **Eval honesty.** The same agent writes both the documents and the questions, which makes it too easy to write questions that copy the source wording.
  - Headline questions must **paraphrase** the source rather than reuse its sentences.
  - At least 8 of the 25 must use vocabulary that differs from the page, as a staff member would phrase it. For example, ask about "how many young people found jobs" when the page says "عدد المستفيدين الملتحقين بسوق العمل".
  - Otherwise the lexical channel inflates the score the client judges us on.
- The executor must write **no lorem ipsum and no `test1`**.

**Owns.** `seed/`, `eval/*.yaml`, `scripts/check_eval.py`.

**Acceptance**
- Every PDF opens and shows correctly shaped Arabic (screenshots of 3 pages in the PR).
- A standalone checker, `scripts/check_eval.py`, extracts text with pypdfium2 and confirms that every `must_include` fact appears on its expected page. It reports 100% before merge.
- Five questions are unanswerable, and at least two of those are near-misses.

**Verify.** `docker compose run --rm api python scripts/check_eval.py eval/questions.yaml eval/dev_questions.yaml`

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
- `clean_extracted`: presentation forms, bidi controls, visual-order repair from S1, header and footer detection.
- `detect_language`.
- `split_sentences` (handles `؟ ، ؛ .`).
- `ARABIC_STOPWORDS` and `lexical_terms(question)`: normalised content terms used to build the OR lexical query in R1.
- Optional `strip_clitics` (و/ب/ل/ال), used only as an E2 sweep variant.
- `normalize_number_tokens` for eval scoring.

**Owns.** `backend/sanad/text/`, `backend/tests/text/`.

**Acceptance.** 100% branch coverage on the module. Required cases:
- `normalize_for_search("التعليــم") == normalize_for_search("التعليم")`
- the diacritised form `"التَّعْلِيم"` matches as well
- alef and hamza variants
- presentation-form input
- mixed `YEP-2021-03` inside Arabic is kept intact

**Verify.** `docker compose run --rm api pytest backend/tests/text -q --cov=sanad.text --cov-fail-under=100`

### B2 · Schema, migrations, auth, roles, users
**Scope.**
- Alembic migrations for SYSTEM_DESIGN §4.
- An `init` one-shot that runs migrations, seeds the admin, editor, viewer and guest users plus the programmes, then registers the seed documents as `queued` with `is_seed=true`.
- Auth (argon2id, session cookie, guest login, rate limiting).
- Role dependency guards.
- `/me`.
- `/admin/users`.
- The error-code registry, with a test that every code exists in `ar.json` and `en.json`.

**Owns.** `backend/sanad/{core,api/auth,api/me,api/admin}`, `backend/alembic/`, `backend/tests/api/`.

**Acceptance**
- A permission-matrix test covers all three roles plus guest against every route.
- Guest with `GUEST_MODE=seed_only` cannot read a non-seed document by id (404).
- A deactivated user's session is rejected.

**Verify.** `docker compose run --rm api pytest backend/tests/api -q`

### B3 · Ingestion pipeline and `ml` service
**Scope.**
- Upload endpoint: magic-byte check, size limit, sha256 duplicate check, `replaces_document_id`.
- Worker claim loop and stale-claim recovery.
- DOCX/TXT → PDF conversion.
- Extract, clean, chunk (D1 parameters from config), embed, store.
- Error codes per SYSTEM_DESIGN §5.2.
- Retry, archive and unarchive endpoints, and version supersede.
- Real `ml` `/embed` and `/rerank` using the S2 choice, with weights baked in at build and offline at runtime.

**Owns.** `backend/sanad/ingest/`, `backend/sanad/api/documents.py`, `ml/`, `backend/tests/ingest/`.

**Acceptance**
- Uploading all `seed/bad/*` fixtures yields `failed` rows with the right codes, and no stack trace appears in any API response.
- The seed corpus reaches `ready` on first boot.
- A killed worker mid-document recovers on restart.
- Page numbers in `chunks` match the viewer PDF.

**Verify**
```
docker compose up -d && docker compose run --rm api pytest backend/tests/ingest -q
docker compose exec db psql -U sanad -c "select status, error_code, count(*) from documents group by 1,2"
```

---

## Retrieval and answering

### R1 · Ask pipeline
**Scope.**
- Dense and lexical retrieval, RRF, rerank, and the three-band gate (D4).
- The lexical query is an **OR of `lexical_terms()`**, ranked with `ts_rank_cd`. Never use `plainto_tsquery` on the raw question, because it ANDs every word, including stopwords (SYSTEM_DESIGN §6).
- Providers: `ollama` (temperature 0), `anthropic` (official SDK), `openai_compat`.
- For the `anthropic` provider, **load the `claude-api` skill before writing it**. Don't send `temperature` or `top_p`, which now return HTTP 400.
- System prompt with `NO_ANSWER` sentinel and injection guard.
- Marker validation, citations, persistence.
- `POST /ask`, `POST /ask/stream` (SSE), `GET /queries`.

**Owns.** `backend/sanad/{retrieval,llm}/`, `backend/sanad/api/{ask,queries}.py`, `backend/tests/retrieval/`.

**Acceptance**
- Unit tests with a fake LLM cover: out-of-range markers dropped; no markers ⇒ `no_answer`; sentinel ⇒ `no_answer`; below `T_refuse` ⇒ the LLM is never called.
- An integration test against the seed corpus answers one Arabic and one English question with correct citations.
- A seed document containing "ignore previous instructions…" does not change the system's behaviour.

**Verify.** `docker compose run --rm api pytest backend/tests/retrieval -q`, plus `curl` of `/api/ask` as guest with an Arabic question.

---

## Frontend

### F1 · App shell
**Scope.**
- Router, TanStack Query, i18next with `ar.json` and `en.json`, `dir`/`lang` sync, and the `?lang=` entry point.
- Radix `DirectionProvider`.
- `useFormat()` (Intl).
- `src/lib/bidi.ts` and the `<Bidi>` component.
- Layout and navigation by role.
- Login page with the language switch visible before login, plus a "Continue as guest" button.
- Self-hosted fonts.
- Generated API types.

**Owns.** `frontend/src/{app,lib,styles}/`, `frontend/src/features/auth/`, `frontend/src/locales/` (shared: later tasks add keys only).

**Acceptance**
- Switching language re-renders without any network request: Playwright asserts that no `/api/*` calls happen on switch.
- The layout mirrors, and a screenshot pair is in the PR.
- The bidi fixture string renders in the correct order.

### F2 · Ask screen
**Scope.** Question box (Enter submits), streaming answer, the three outcome states (D4 copy), citation cards (title, page, snippet, linking to the viewer), and the history side panel.

**Owns.** `frontend/src/features/ask/`.

### F3 · Library and Upload
**Scope.**
- Library table with title, file type, category, year, programme, uploaded by, date, page count and status; filters, search and paging; row click opens the viewer; archive, retry and "upload new version" actions.
- Upload screen with drag and drop, multiple files, 3 concurrent, per-file stage chips, and the failure reason translated from `error_code`.

**Owns.** `frontend/src/features/{library,upload}/`.

### F4 · Document viewer
**Scope.** pdf.js viewer that opens at `?page=N` and highlights the `chunk` span using the S4 method, with a page-level fallback; also lists earlier versions.

**Owns.** `frontend/src/features/viewer/`.

### F5 · Admin
**Scope.** User list and create/edit (role, active, language), and a usage log table (user, question, outcome, time) with filters.

**Owns.** `frontend/src/features/admin/`.

**Verify for F1–F5.**
- `make lint && make test-frontend`
- The Playwright smoke test `npx playwright test e2e/smoke.spec.ts` covers: login → ask Arabic question → click the first citation → viewer on the expected page, all in ≤2 clicks after login.

---

## Evaluation

### E1 · Eval runner
**Scope.**
- `python -m sanad.eval` per SYSTEM_DESIGN §11: scoring, recall@K diagnostics, and Markdown and JSON reports with a per-question table and a failure category (retrieval / generation / refusal) for each failure.
- Local runs are deterministic (Ollama at temperature 0). API-mode runs can't pin sampling, so the runner supports `--repeat N` and reports the mean and the range for that mode.

**Verify.** `docker compose run --rm api python -m sanad.eval --set test` prints `Score: X/25` and writes `eval/results/*.md`.

### E2 · Tuning
**Scope.**
- On the **dev** set only: the chunk sweep (D1), threshold tuning (D4), and lexical config `simple` vs `arabic`.
- Then exactly one headline run per configuration we report: the local default, and Claude if P3 allows.
- Write the measured numbers into DECISIONS.

**Acceptance.** The results tables are committed, and DECISIONS no longer has *est.* values for anything that was measured.

---

## Hardening and delivery

### H1 · Bulk upload resilience
**Scope.** A Playwright test that uploads 50 files (45 good, plus the 5 `seed/bad` fixtures) and asserts that every good file reaches `ready`, every bad one shows a readable reason, and the batch never stalls.

### H2 · Clean-machine and egress test
**Scope.**
- Fresh clone into an empty directory, then bring it up under its own project name (`docker compose -p sanad-cleantest up`) so it can't share volumes with the dev stack. Tear it down afterwards with `docker compose -p sanad-cleantest down -v`.
- Time it until the seed corpus is ready and the guest can get an answer.
- Verify there is no egress from `api`, `worker`, `ml`, `db` or `ollama`, using the base compose file.
- If first boot takes more than about 5 minutes on reference hardware, ship a pre-computed seed index.

### H3 · README and acceptance run
**Scope.**
- README sections:
  - quick start for the IT person
  - stack justification
  - chunking rationale
  - **Decisions** (from DECISIONS.md)
  - eval results, including the questions that fail and why
  - configuration reference
  - backup and restore
  - limitations
- Then run the brief's §12 acceptance checklist and record the evidence for each item.
