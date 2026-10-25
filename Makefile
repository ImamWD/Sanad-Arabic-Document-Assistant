# Sanad developer entry points. Everything runs in containers: host Python and Node are
# never needed. Tool containers (profile `tools`) bind-mount the repo, so they see the
# working tree as it is, including uncommitted files.

# --- instance -----------------------------------------------------------------------------
# SANAD_INSTANCE is the compose project name and the tag of every image we build, so two
# checkouts never share containers, volumes or images (see docker-compose.yml).
#   main checkout: nothing is set here, so make and plain `docker compose` drive the same
#                  stack: SANAD_INSTANCE=sanad, WEB_PORT=8080 (or whatever .env says).
#   git worktree:  SANAD_INSTANCE=sanad-<directory name>, WEB_PORT derived from it (8100-8899).
# Override either on the command line: make up SANAD_INSTANCE=sanad-demo WEB_PORT=8081
GIT_DIR := $(shell cd "$$(git rev-parse --git-dir 2>/dev/null)" 2>/dev/null && pwd -P)
GIT_COMMON_DIR := $(shell cd "$$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd -P)
ifneq ($(GIT_DIR),$(GIT_COMMON_DIR))
DIR_SLUG := $(shell basename "$(CURDIR)" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9_\n-' '-')
SANAD_INSTANCE ?= sanad-$(DIR_SLUG)
WEB_PORT ?= $(shell printf '%s' '$(SANAD_INSTANCE)' | cksum | awk '{ print 8100 + $$1 % 800 }')
export SANAD_INSTANCE WEB_PORT
endif

COMPOSE ?= docker compose
# Base file plus the development override (hot reload, route to host Ollama; NOT isolated).
DEV_COMPOSE := $(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml
RUN := $(COMPOSE) run --rm -T
NODE := $(RUN) node sh -c
UV_IMAGE := ghcr.io/astral-sh/uv:0.13.5-python3.12-trixie-slim

.DEFAULT_GOAL := help
.PHONY: help info up up-dev down logs lint lint-style lint-backend lint-ml lint-frontend test \
	test-backend test-ml test-frontend test-e2e fmt gen-api-types check-api-types lock \
	render-smoke render-seed check-eval tools-build eval eval-dev

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

info: ## Show which instance (compose project) and port this checkout uses
	@echo "SANAD_INSTANCE=$${SANAD_INSTANCE:-sanad (compose default)}"
	@echo "WEB_PORT=$${WEB_PORT:-8080 (compose default, unless .env sets it)}"

up: ## Build and start the stack, wait until healthy, print its URL
	$(COMPOSE) up -d --build --wait
	@echo "Sanad is up: http://$$($(COMPOSE) port web 8080 | sed 's/^0\.0\.0\.0/localhost/')"

up-dev: ## Like up, plus docker-compose.dev.yml (hot reload, host Ollama). Relaxes isolation!
	$(DEV_COMPOSE) up -d --build --wait
	@echo "Sanad (dev override) is up: http://$$($(COMPOSE) port web 8080 | sed 's/^0\.0\.0\.0/localhost/')"

down: ## Stop the stack, dev override included (data volumes are kept)
	$(DEV_COMPOSE) down

logs: ## Follow logs of the running stack
	$(COMPOSE) logs -f

tools-build: ## Build the dev tool images
	$(COMPOSE) --profile tools build backend-dev ml-dev

# --- lint ---------------------------------------------------------------------------------

lint: lint-style lint-backend lint-ml lint-frontend ## ruff + mypy, ESLint + stylelint + tsc + prettier, gate self-test

lint-style: ## Owner writing rule: no em dash in code comments, UI text or README
	sh scripts/check-no-em-dash.sh

lint-backend: tools-build
	$(RUN) --no-deps -w /app/backend backend-dev sh -c 'ruff check . && ruff format --check . && mypy'

lint-ml: tools-build
	$(RUN) -w /app/ml ml-dev sh -c 'ruff check . && ruff format --check . && mypy'

lint-frontend:
	$(NODE) 'sh scripts/ensure-deps.sh && npm run lint && sh scripts/check-lint-gates.sh'

# --- test ---------------------------------------------------------------------------------

test: test-backend test-ml test-frontend ## All unit tests (no running stack needed)

test-backend: tools-build
	$(RUN) -w /app/backend backend-dev pytest -q

test-ml: tools-build
	$(RUN) -w /app/ml ml-dev pytest -q

test-frontend: ## vitest (Playwright needs the running stack: make test-e2e)
	$(NODE) 'sh scripts/ensure-deps.sh && npm test'

test-e2e: ## Playwright against the running stack (run `make up` first)
	$(NODE) 'sh scripts/ensure-deps.sh'
	$(RUN) e2e npx playwright test

# --- format / codegen ---------------------------------------------------------------------

fmt: tools-build ## Auto-format and auto-fix Python and frontend code
	$(RUN) --no-deps backend-dev sh -c 'ruff check --fix backend ml && ruff format backend ml'
	$(NODE) 'sh scripts/ensure-deps.sh && npm run format'

gen-api-types: tools-build ## Regenerate frontend/src/api/{openapi.json,schema.d.ts} from the API
	$(RUN) --no-deps backend-dev python -m sanad.api.openapi > frontend/src/api/openapi.json
	$(NODE) 'sh scripts/ensure-deps.sh && npm run gen:api-types'

check-api-types: gen-api-types ## Fail if the committed API types are stale
	git diff --exit-code -- frontend/src/api/

lock: ## Re-resolve uv.lock (backend, ml) and package-lock.json after editing dependencies
	docker run --rm -v "$(CURDIR)/backend:/src" -w /src -e UV_PYTHON_DOWNLOADS=never $(UV_IMAGE) uv lock
	docker run --rm -v "$(CURDIR)/ml:/src" -w /src -e UV_PYTHON_DOWNLOADS=never $(UV_IMAGE) uv lock
	$(NODE) 'npm install --no-audit --no-fund'

# --- document rendering (C1b) -------------------------------------------------------------

render-smoke: ## Render an Arabic HTML snippet to PDF with the render tools image
	$(COMPOSE) --profile tools build render
	$(RUN) render sh tools/render/smoke.sh

render-seed: ## Render seed/sources into seed/documents, seed/bad and seed/previews (deterministic)
	$(COMPOSE) --profile tools build render
	$(RUN) render python3 seed/render.py

# Runs in backend-dev: the worker's own LibreOffice, fonts and extractors (B3), so the check
# covers the conversions and text ingestion really uses. Default: the worker's extractor.
EVAL_ARGS ?= --extractor poppler
check-eval: tools-build ## Check eval/*.yaml against the seed corpus as ingestion converts it (EVAL_ARGS="--extractor pdfium")
	$(RUN) --no-deps backend-dev python scripts/check_eval.py $(EVAL_ARGS) eval/questions.yaml eval/dev_questions.yaml

# --- evaluation (E1) ----------------------------------------------------------------------

# Score the running stack (`make up` first) end to end over HTTP, signed in as the demo editor.
# Reports go to eval/results/; the last line printed is `Score: X/N`. Extra flags, e.g.
#   make eval EVAL_FLAGS="--hardware 'M5 MacBook, CPU, 8 GB stack' --repeat 3"
# The container has no git, so the commit under test is passed in from here.
EVAL_GIT_SHA ?= $(shell git rev-parse --short=12 HEAD 2>/dev/null)$(shell git diff --quiet HEAD 2>/dev/null || echo -dirty)
eval: tools-build ## Score the 15 headline questions against the running stack (EVAL_FLAGS="--hardware ...")
	$(RUN) --no-deps backend-dev python -m sanad.eval --set test --git-sha "$(EVAL_GIT_SHA)" $(EVAL_FLAGS)

eval-dev: tools-build ## Score the 30 dev (tuning) questions against the running stack
	$(RUN) --no-deps backend-dev python -m sanad.eval --set dev --git-sha "$(EVAL_GIT_SHA)" $(EVAL_FLAGS)
