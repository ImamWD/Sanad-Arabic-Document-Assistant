# Roadmap: two-week portfolio build

**Scope and schedule are set by [BUILD_PLAN.md](BUILD_PLAN.md), Part 1.** Behaviour is set by its Part 2, the decisions log. Where anything below disagrees with BUILD_PLAN, BUILD_PLAN wins.

**How we work**
- The project manager (Claude) plans, reviews and verifies. Executor Claude Code agents implement.
- Each executor reads, in order:
  1. [`CLAUDE.md`](../CLAUDE.md)
  2. `BUILD_PLAN.md`
  3. [`DECISIONS.md`](DECISIONS.md) and [`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md), for detail
  4. its own brief below
- Each executor works on a branch `task/<ID>-<slug>`. When done, it pushes the branch and opens a PR to `main`, with its final report as the PR description.
- Executors never push to `main` and never merge.
- The manager re-runs the **Verify** commands, reviews the diff and merges with the owner's go-ahead. No task is "done" on the executor's word alone.

## Schedule

| Week | Dates | Work |
|---|---|---|
| 1 | 26 Oct – 1 Nov | Finish C1b, B1, F1 and S3. Then B2 and B3 in parallel; R1 starts after B2; F2 starts after F1. Bilingual shell, ingestion, chunking, embeddings, retrieval, Ask screen. |
| 2 | 2 – 8 Nov | R1, F2, then F3, F4, F5, E1, E2, H2, H3: roles, Library, viewer, refusal gate, evaluation, Docker, README. |
| — | **~8 Nov** | **Sanad complete and published to the portfolio.** |

## Definition of done (from BUILD_PLAN)

- [ ] `docker compose up` works on a clean machine, and the README states the RAM it needs
- [ ] The guest account (`?lang=en`) reaches a working answer with a citation in under three clicks
- [ ] The language toggle mirrors the whole interface without losing state
- [ ] The eval script runs on **15 headline questions** and reports a score; failures are documented in the README
- [ ] Refusal is demonstrable: a question with no answer in the corpus produces a refusal, not an invention
- [ ] The README has a Decisions section, the deferred list, the data-handling rule and the network-isolation paragraph

**Never cut:** the refusal gate and the evaluation score. If time runs short, reduce the question count; never remove the harness.

## Deferred to v2 (listed in the README, not built)

- Document versioning, superseded handling, the amendment chain
- Paragraph-level highlighting (page-level is enough)
- The detailed Admin usage log, the outcome summary and 12-month retention
- Bulk upload with per-file progress states (a simple multi-file upload is enough)
- Everything GPU: procurement, benchmarking, tier tables
- API-mode provider switching (keep the abstraction and the override; ship local only)
- Spikes S1, S2 and S4, G1, H1 and H4 from the earlier plan:
  - extraction library decided: **pypdfium2**
  - embedding model decided: **bge-m3**

## Dependencies

```
M0 ✅ ─┬─ C1b render ───────────────────────────────┐
C1a ✅ ┘                                             │
        ├─ B1 arabic text ──┐                       │
        ├─ B2 schema/auth/roles ─┬─ R1 ask + gate ──┼─ E1 eval ─ E2 thresholds ─ H2 clean machine ─ H3 README
        │                        │        ▲         │
        ├─ B3 ingestion + ml ────┴────────┘         │
        ├─ S3 model choice ──────────────►R1        │
        └─ F1 shell ─ F2 ask ─ F3 library/upload ─ F4 viewer ─ F5 users
```

**File ownership.** Writers never share files, with one exception: the **shared append-only files**, which any task may *add to* only. The manager merges them and re-locks.
- `frontend/src/locales/ar.json` and `en.json` (always add to both)
- `.env.example`
- `backend/sanad/core/errors.py`
- the router list in `backend/sanad/api/main.py`
- `backend/tests/api/test_permissions.py` (matrix rows)
- the step list in `backend/sanad/init.py`
- the dependency manifests and their lockfiles

**Alembic revisions are fixed so B2, B3 and R1 can work in parallel:**

| Revision | Owner | Contents |
|---|---|---|
| `0001_core` | B2 | users, sessions, programmes, audit_events |
| `0002_documents` (`down_revision = "0001_core"`) | B3 | the pgvector extension, documents, document_pages, chunks |
| `0003_queries` (`down_revision = "0002_documents"`) | R1 | queries, citations, llm_perf_samples |

---

## Done

- **M0** (scaffold, compose, lint gates, plus the M0b fixes). Merged.
- **C1a** (30 synthetic documents, eval sets). Merged.

## In progress

### C1b · Render seed corpus and eval checker
Brief as sent.
- Render PDF, DOCX and TXT from `seed/sources`, with one source page per rendered page.
- `seed/bad/` fixtures.
- `scripts/check_eval.py` (pypdfium2, run in the `render` image), which must report 100%.

**Additions (new scope):**
- In `seed/manifest.json`, mark **1–2 documents `restricted: true`**. One of them must hold a fact that **only** it contains, for the R1 restricted-retrieval test.
- Mark the draft budget **`archived: true`**, so it stays out of retrieval, because versioning is deferred.

### B1 · Arabic text library
Brief as sent: `normalize_for_search`, `clean_extracted`, `detect_language`, `split_sentences`, stopwords and `lexical_terms`, `strip_clitics`, `normalize_number_tokens`, at 100% branch coverage.

### F1 · App shell
Brief as sent, plus these rulings:
- **The fallback locale is English** (`en`). The guest link is `?lang=en`.
- **Digits are Latin by default in both languages** (`AR_NUMBERING=latn`).
- A language switch makes no data GET. `PATCH /me` is sent for real users only.

### S3 · Model choice (trimmed)
- 2–3 models, the 10 existing prompts, about a day of work.
- **The question to answer:** which default model, together with fp16 or int8 weights in `ml`, fits the **whole stack in about 8 GB** of Docker memory with acceptable quality? Plus an optional larger model for GPU hosts such as the owner's RTX 5080.
- No RTX PRO 4000 projection. The Gemini reference run is optional.

---

## Next

### B2 · Schema, auth, roles, restricted flag, guest
**Scope.**
- Alembic `0001_core`: users (with `preferred_language`, `is_guest`, `is_active`), sessions, programmes, audit_events.
- The `init` service runs `alembic upgrade head`, then `python -m sanad.init`.
  - `sanad/init.py` runs a list of steps. B2 adds the steps that seed users and programmes; later tasks append their own steps.
  - Seed accounts: admin, editor, viewer and **guest**, with demo passwords in `.env.example` and the README.
- Auth: argon2id, an opaque session cookie (httpOnly, SameSite=Lax), login and logout, **guest login**, and login rate limiting.
- `sanad/core/security.py` provides `get_current_user`, `require_role(*roles)` and the user model, with `.role` and `.is_guest`. B3 and R1 code against this contract.
- Endpoints: `/me` (GET and PATCH `preferred_language`), `/admin/users` (list, create, edit role/active/language, no delete), `GET /programmes`.
- **Document categories enum:**
  - annual_report
  - donor_agreement
  - programme_evaluation
  - field_survey
  - budget
  - board_minutes

  There is **no `other`**. A NULL category means uncategorised, which the Library flags for review.
- Error-code registry, with a test that every code is translated in both locales.

**Owns.** `backend/sanad/{core,api/auth.py,api/me.py,api/admin_users.py,api/programmes.py,init.py}`, `backend/alembic/` (0001 and env), `backend/tests/api/`, the `init` service.

**Acceptance**
- A permission-matrix test covers viewer, editor, admin and guest.
- A deactivated user's session is rejected.
- The guest can't call editor or admin routes.
- A test pins the D4 approved refusal and low-confidence strings in both locales.

**Verify.** `docker compose run --rm backend-dev pytest backend/tests/api -q`, plus `make lint`.

### B3 · Ingestion pipeline and `ml` service
**Scope.**
- Alembic `0002_documents`: documents, with `file_type`, `category`, `year`, `programme_id`, `restricted`, `is_archived`, `is_seed`, `status`, `error_code` and `error_params`; document_pages; chunks with a pgvector embedding and the generated `tsv`.
- **Real `ml` service**:
  - `/embed` (bge-m3) and `/rerank` (bge-reranker-v2-m3)
  - weights baked in at build time, offline at runtime
  - fp16 or int8 per S3's memory answer
- **Upload API** (editor+): one file per request, magic-byte check, size limit and sha256 duplicate check, with category, year, programme and the `restricted` flag.
- **Lifecycle endpoints:**
  - `PATCH` for metadata
  - archive and unarchive
  - retry
- **Read endpoints:**
  - `GET /documents`, with filters on title search, file type, category, year, programme and status
  - `GET /documents/{id}`, `/file` and `/pages/{n}`

  All of them apply `sanad.documents.access.visible_documents(user)`, which R1 reuses:
  - Viewers never see restricted documents (404 on direct access).
  - The guest sees seed documents only, and never restricted ones.
  - Archived documents are excluded by default.
- **Worker:**
  - claim loop and stale-claim recovery
  - DOCX → PDF via LibreOffice
  - TXT decoded in Python (utf-8 → utf-8-sig → cp1256), then LibreOffice
  - extract with **pypdfium2**, clean with B1, chunk per D1 with page-bounded chunks, embed, store
  - error codes per SYSTEM_DESIGN §5.2, including `NO_TEXT_LAYER`
- **The `init` step that registers the seed corpus** from `seed/manifest.json`, honouring the `restricted` and `archived` flags.
- **Conversion parity:** the worker image uses the same LibreOffice and fonts as C1b's checker, and the checker still reports 100% against the worker's own conversions.

**Before B2 merges:** build `ml`, and the extract/clean/chunk/embed modules with their unit tests. Wire up the DB and auth parts after rebasing on B2.

**Owns.** `backend/sanad/{ingest,documents}/`, `backend/sanad/api/documents.py`, `backend/alembic/versions/0002_*`, `ml/`, `backend/tests/ingest/`, and LibreOffice plus fonts in `backend/Dockerfile`.

**Acceptance**
- Every `seed/bad/*` fixture fails with the correct code, and no stack trace appears in any response.
- The seed corpus reaches `ready` on first boot.
- Chunk page numbers match the viewer PDF.
- A viewer can't list or open a restricted document.
- The guest sees seed documents only.

**Verify.** `make up && docker compose run --rm backend-dev pytest backend/tests/ingest -q`

### R1 · Ask pipeline and refusal gate
**Scope.**
- Alembic `0003_queries`.
- **Retrieval:** dense plus lexical (an OR of `lexical_terms()`, `ts_rank_cd`), RRF, rerank, the three-band gate (D4), always through `visible_documents(user)`.
- **Prompt and validation:**
  - prompt contract with the `NO_ANSWER` sentinel and an injection guard
  - marker validation, so no valid `[n]` means no answer
  - `refusal_reason` set to `gate`, `sentinel` or `no_valid_citation`
  - citations carry `file_type` and `is_converted`
  - refusals carry up to 3 `nearest_documents`
- **Providers:** `ollama` (shipped default, temperature 0); keep the `openai_compat` and `anthropic` adapters behind the override, unused by default. Hosted calls with non-seed excerpts are refused in code.
- **Endpoints:**
  - `POST /ask`
  - `POST /ask/stream` (SSE) with the SYSTEM_DESIGN §6 events: stages, `band` on `reading`, `eta`, `writing` on the first token, sentinel held back, `final` replaces the streamed text
  - `GET /queries` (own history)
- **Compose:** the `ollama` and `ollama-init` services (the S3 default model), `docker-compose.api-llm.yml`, and the nginx stream settings.

**Owns.** `backend/sanad/{retrieval,llm}/`, `backend/sanad/api/{ask,queries}.py`, `backend/alembic/versions/0003_*`, `backend/tests/retrieval/`, and the compose items above.

**Acceptance**
- **Fake-LLM tests:**
  - out-of-range markers are dropped
  - no valid marker ⇒ refusal
  - the sentinel ⇒ refusal, with no tokens streamed
  - below `T_refuse`, the LLM is never called
- **Stream order** is as specified.
- **Restricted retrieval:** a **viewer asking the question that only a restricted seed document answers gets a refusal**, while an editor gets the answer.
- **Prompt injection:** the injection fixture doesn't change behaviour.
- **Integration:** one Arabic and one English seed question are answered with correct citations.

**Verify.** `docker compose run --rm backend-dev pytest backend/tests/retrieval -q`, and `curl -N` of `/api/ask/stream` as the guest.

### F2 · Ask screen
**Scope.**
- Question box (Enter submits), streamed answer, the three outcome states with the D4 approved copy.
- **The refusal message states its reason:** "the documents don't cover this" (`gate`) versus "nothing usable was found in what was read" (`sentinel` or `no_valid_citation`), plus up to 3 "you may want to check" titles.
- Never looks frozen:
  - stage text
  - the ETA notice when the estimate is over 20 s
  - elapsed time against the estimate
  - the amber banner from the `reading` event onward
  - streamed text replaced when the outcome is `no_answer`
- Citation cards (title, page, snippet) that open the viewer at that page, with a converted-file note for DOCX and TXT sources.
- History side panel.
- Until R1 merges, it works against a `page.route` mock of the stream.

**Owns.** `frontend/src/features/ask/`, `frontend/e2e/ask-*.spec.ts`.

### F3 · Library and upload
**Scope.**
- **Library table:** title, file type, category (uncategorised is flagged), year, programme, uploaded by, date, page count, **status**, and a restricted badge.
  - Filters and search. Row click opens the viewer.
  - Editor actions: archive, retry, toggle restricted, edit metadata.
- **Simple multi-file upload:** each file is a separate request. The status list refreshes by polling, and failures show their translated reason.

**Owns.** `frontend/src/features/{library,upload}/`, `frontend/e2e/{library,upload}-*.spec.ts`.

### F4 · Document viewer (page-level)
**Scope.**
- A pdf.js viewer that opens at `?page=N`, marks the cited page and scrolls to it.
- The converted-file note.
- The smoke test: guest → Arabic or English question → first citation → viewer on the expected page, in ≤2 clicks after login.

**Owns.** `frontend/src/features/viewer/`, `frontend/e2e/viewer-*.spec.ts`, `frontend/e2e/smoke.spec.ts`.

### F5 · Admin: users and roles
**Scope.** User list, plus create and edit (role, active, language). Numbers and dates go through `useFormat()`. The detailed usage log is v2.

**Owns.** `frontend/src/features/admin/`, `frontend/e2e/admin-*.spec.ts`.

**Verify for F2–F5.** `make lint && make test-frontend && make up && make test-e2e`

### E1 · Eval runner (15 headline questions)
**Scope.**
- `python -m sanad.eval --set test|dev [--model …] [--repeat N]`, scored per SYSTEM_DESIGN §11.
- Recall@K diagnostics, and a failure category for each failure: retrieval / generation / refusal / page-split.
- Markdown and JSON reports that record the model, hardware label, Ollama version and date.

**Owns.** `backend/sanad/eval/`, `backend/tests/eval/`.

**Verify.** `docker compose run --rm backend-dev python -m sanad.eval --set test` prints `Score: X/15`.

### E2 · Threshold tuning
**Scope.**
- Tune `T_REFUSE` and `T_CONFIDENT` on the **dev** set only (30 questions).
- Then run the headline set once on the shipped default model, and once on the larger model if S3 names one. Label each run with its hardware.

**Owns.** `eval/results/`, and the threshold defaults in config and `.env.example`.

### H2 · Clean machine
**Scope.**
- Fresh clone, then `docker compose -p sanad-cleantest up`, timed until the guest gets an answer.
- Measure peak memory, which goes into the README.
- No egress from content containers with the base compose file.
- Tear down with `down -v`.

**Owns.** `scripts/cleantest.sh`.

### H3 · README (English)
**Scope.**
- Positioning: "works correctly in both directions".
- Quick start, the guest link `?lang=en`, and the RAM requirement.
- Stack and chunking rationale.
- **Decisions** (from BUILD_PLAN Part 2 and DECISIONS.md), containing verbatim *"Cost is not the reason to stay local; privacy is."*
- Eval score and failures, with hardware labels.
- **Deferred to v2** list.
- **The data-handling rule, verbatim** (BUILD_PLAN Part 2).
- **"Can documents leave the server?"**: the network-isolation paragraph.
- A placeholder for the language-toggle clip.

**Owns.** `README.md`.

**Verify.** `grep -F 'Cost is not the reason to stay local; privacy is.' README.md && grep -F 'Can documents leave the server?' README.md`
