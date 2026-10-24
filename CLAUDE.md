# Sanad — house rules for executor agents

You are implementing one task from [docs/ROADMAP.md](docs/ROADMAP.md). Before writing code, read:
1. [docs/brief.md](docs/brief.md), the client's original requirements
2. [docs/DECISIONS.md](docs/DECISIONS.md), the client's approved decisions (24 Oct 2026). Where a decision differs from the brief, the decision wins. Examples: no API mode for client documents, the three-band refusal gate with its approved wording, version history, the never-frozen Ask screen.
3. [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md)
4. your task brief in ROADMAP.md, including its **Owns** list, acceptance criteria and **Verify** commands

If the design and your task disagree, or a product decision is missing, **stop and ask the manager**. Don't guess, and don't silently redesign.

## Non-negotiables

1. **No literal UI strings.** Every user-visible string goes through `t()` with keys in `frontend/src/locales/ar.json` **and** `en.json`, added together in the same commit. ESLint `i18next/no-literal-string` is an error. Do not disable it inline.
2. **CSS logical properties only.** Use `margin-inline-start`, `padding-inline-end`, `inset-inline-start`, `text-align: start`, `border-start-start-radius` and so on. Never use `left`, `right`, `margin-left`, `padding-right` or `text-align: left`. Stylelint enforces this.
3. **`dir` follows the locale** and is set on `<html>`. Don't set `dir` elsewhere except `dir="auto"` on content blocks: answers, snippets, titles and filenames.
4. **Dates, numbers and currency are formatted through `Intl`**, via `useFormat()`. Never concatenate or hand-format them.
5. **All Arabic matching goes through `sanad.text.arabic`.** Never write ad-hoc regexes for diacritics, alef, hamza or tatweel anywhere else. If a function is missing, add it there, with tests.
6. **The server returns error codes, never prose.** Use `{"error": {"code": "UPPER_SNAKE", "params": {...}}}`. Ingestion failures use `error_code` and `error_params`. Every code needs a translation in both locale files, and a test enforces this. Stack traces go to server logs only.
7. **No document content leaves the server.**
   - No external HTTP calls from `api`, `worker` or `ml` at runtime. The only exception is a hosted LLM adapter in API mode, which may only ever carry synthetic seed data and is never deployed where client documents live. A code guard enforces this (`HOSTED_LLM_NON_SEED_DATA`), so don't weaken it.
   - No CDN assets, fonts or analytics.
   - `HF_HUB_OFFLINE=1` at runtime.
8. **Never invent answers.** Don't weaken the refusal path: the gate, the `NO_ANSWER` sentinel, and the rule that no valid citation means no answer. Changes to prompts or thresholds go through the eval (`python -m sanad.eval --set dev`), with before and after numbers in the PR.
9. **The repo is public.**
   - Never commit real client documents, secrets, `.env` files, model weights or anything under `data/`.
   - Seed data is synthetic and *obviously* fake where it's personal (names, IDs, salaries).
   - Seed content is realistic Arabic and English. No lorem ipsum, no `test1`.

## Environment

- Run Python **in containers** (Python 3.12). The host's `python3` is 3.9: don't use it for project code. Use `make` targets or `docker compose run --rm backend-dev …` (the dev image: same Python env as `api` plus test tools, repo mounted, starts at the repo root). The `api` image is a slim runtime and has no pytest.
- Dev machines are Apple Silicon (arm64). The production server is probably x86-64. Don't add an image or dependency without both architectures.
- Docker on macOS has no GPU. For fast local LLM runs in dev, use host-native Ollama through `OLLAMA_BASE_URL=http://host.docker.internal:11434`. That only works with `docker-compose.dev.yml`, which gives `api` a non-internal network. Egress and isolation tests always run against the base `docker-compose.yml`.
- **Claude API code** (the `anthropic` provider adapter, or anything else that calls Claude): load the `claude-api` skill before writing it, and use the official `anthropic` SDK. Don't send `temperature`, `top_p` or `top_k`; they now return HTTP 400.
- **Downloads** (allowed by the owner for testing, e.g. public Arabic PDFs):
  - Put them only in `spikes/_downloads/`, which is inside the project folder and git-ignored.
  - Treat them as untrusted and never execute them.
  - Commit a manifest (URL, sha256, licence) and a fetch script, so the manager can re-fetch the files to verify.
  - **Delete them when they're no longer needed**, after the manager's verification. Your report lists what was downloaded.
  - **Model weights** pulled for a spike go only into the git-ignored `/models/` or `/hf_cache/` folders, or a named Docker volume. At the end, remove the models that weren't chosen (`ollama rm …`, delete their cache entries) and list them.
- **Client sample documents** (`data/client-samples/`, git-ignored) are the client's real reports.
  - Never commit them, and never send them to any API.
  - **Never read their text, titles or file names into your context**: no `cat`, no Read tool, no printing excerpts, no psql or API queries that return their rows.
  - Only run scripts whose output is aggregate numbers (rates, counts, timings), written so they never echo document text, even on errors.
  - They are ingested only into the owner's separate stack (`docker compose -p sanad-samples -f docker-compose.yml up -d`, base file only). Never ingest them into the dev stack, and never run that stack with the dev or api-llm overrides.
  - Playwright runs against them use `trace`, `screenshot` and `video` set to `off`, write no HTML report, and name tests by id only.
  - If something needs human eyes, list it for the project owner.
- **Hosted LLM APIs** (the free reference model through `openai_compat`, or `anthropic`) may only ever receive **synthetic seed data**.

## Code conventions

- **Backend**
  - FastAPI routers in `sanad/api/`, business logic outside routers.
  - SQLAlchemy 2.0 and Alembic. Every schema change is a migration.
  - Use pydantic-settings for config. Every new setting goes in `.env.example` with a comment.
  - ruff and mypy must be clean.
- **Frontend**
  - React and TypeScript in strict mode.
  - TanStack Query for server state.
  - Each feature lives in `src/features/<name>/` and only touches its own folder, `src/locales/*` (adding keys), the generated API types, and the `frontend/e2e/` specs its task lists.
  - Playwright runs in the `e2e` tools container (`make test-e2e`), never on host Node.
  - Regenerate the types with `make gen-api-types` after any API change.
- **Tests**
  - Every task adds tests: pytest for the backend, vitest for the frontend, and Playwright for end-to-end flows.
  - Tests use the seed corpus or fixtures, never the network.

## Git and PRs

- Branch `task/<ID>-<slug>` from `main`. Never commit to `main`, never force-push, never rewrite shared history.
- **Pushing (the owner lifted the hold on 24 Oct 2026):** when your task is done, push your `task/<ID>-<slug>` branch and open a PR to `main` with `gh pr create`, using your final report as the body. **Never push to `main` and never merge a PR.** The manager verifies, then merges with the owner's go-ahead.
- Keep commits small and conventional (`feat(ingest): …`, `fix(ask): …`, `test(text): …`).
- Only touch files in your task's **Owns** list, plus the ROADMAP's shared append-only files (locale keys, `.env.example` settings, error codes, router lines, permission-matrix rows), which you may only add to. If you need to change anything else, ask first.
- The PR description (your final report) must contain:
  - what changed
  - the **Verify** commands, with their actual output pasted
  - any acceptance criterion **not** met, and why
  - follow-ups

## Definition of done

- [ ] All acceptance criteria in the task brief are met, or each gap is explicitly listed in the PR
- [ ] `make lint` and `make test` pass
- [ ] Verify commands run, with output in the PR
- [ ] New UI strings exist in both `ar.json` and `en.json`
- [ ] New error codes are translated in both locales
- [ ] New config is documented in `.env.example`
- [ ] Any behaviour that affects answers has before and after eval numbers
- [ ] No secrets, weights or client data in the diff
