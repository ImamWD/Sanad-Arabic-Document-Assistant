# Sanad: Arabic Document Assistant

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

### Several instances side by side (git worktrees)

`SANAD_INSTANCE` is the compose project name and the tag of every image the stack builds,
so two instances never share containers, volumes, networks or images.

| Where | `SANAD_INSTANCE` | `WEB_PORT` |
|---|---|---|
| main checkout, plain `docker compose` or `make` | `sanad` | `8080` (or `.env`) |
| git worktree, via `make` | `sanad-<directory name>` | derived from the name, 8100–8899 |
| anywhere, explicit | your choice | your choice |

```bash
make info                                        # what this checkout uses
make up SANAD_INSTANCE=sanad-demo WEB_PORT=8081  # explicit instance via make
SANAD_INSTANCE=sanad-demo WEB_PORT=8081 docker compose up -d --build   # same, without make
```

Plain `docker compose` inside a worktree still means the default `sanad` instance, i.e. the
same stack as the main checkout. Use `make`, or set `SANAD_INSTANCE`, to keep them apart.
Don't use `COMPOSE_PROJECT_NAME` or `-p` instead: they rename the project but not the image
tags, so two instances would overwrite each other's images.

### Development override

`docker-compose.dev.yml` (or `make up-dev`) bind-mounts the source with hot reload and gives
`api` and `backend-dev` a route to the host, so they can use a host-native Ollama at
`http://host.docker.internal:11434`. It deliberately **relaxes isolation**: never use it in
production. The no-egress guarantee and its tests apply to `docker-compose.yml` alone.
