# Sanad — Arabic Document Assistant

Ask questions in Arabic or English and get answers drawn only from your organisation's own
documents, with page-level citations. Runs entirely on your own server with `docker compose`.

> Work in progress. The design lives in [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) and the
> plan in [docs/ROADMAP.md](docs/ROADMAP.md). The full README (stack rationale, decisions,
> evaluation results, operations) arrives with task H3.

## Quick start

Requirements: Docker with Compose v2. Nothing else: no host Python or Node.

```bash
cp .env.example .env    # optional; every setting has a default
make up                 # docker compose up -d --build --wait
```

Open http://localhost:8080 (Arabic, right-to-left) or http://localhost:8080/?lang=en.
`curl localhost:8080/api/health` returns `{"status":"ok","db":"ok","ml":"ok"}`.

## Development

Every command runs in a container (compose profile `tools`); see `make help`.

| Command | What it does |
|---|---|
| `make lint` | ruff + mypy (backend, ml); tsc, ESLint, stylelint, prettier (frontend); lint-gate self-test |
| `make test` | pytest (backend, ml) and vitest (frontend) |
| `make test-e2e` | Playwright against the running stack (`make up` first) |
| `make fmt` | auto-format Python and frontend code |
| `make gen-api-types` | regenerate `frontend/src/api/schema.d.ts` from the FastAPI spec |
| `make lock` | re-resolve `uv.lock` and `package-lock.json` after a dependency change |
| `make render-smoke` | render Arabic HTML to PDF/DOCX with the render tools image |

Isolation: `db`, `api`, `worker` and `ml` sit on the `backend` network, which is
`internal: true`, so they cannot reach the internet. Only `web` publishes a port.
