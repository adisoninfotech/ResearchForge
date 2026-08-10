# ResearchForge

Evidence-grounded research manuscript platform — monorepo foundation for local development, authentication scaffolding, guest workspace, health checks, and CI.

Guests explore with a browser-local draft. Saving, permanent uploads, full exports, full similarity checks, and full section generation require authentication. User content is private by default and is never used for model training without explicit opt-in. Similarity checks do **not** guarantee zero plagiarism.

## Repository layout

```
apps/
  web/                 Next.js App Router frontend
  api/                 FastAPI + Celery backend
packages/
  shared-types/        Shared TypeScript contracts
  ui/                  Accessible UI primitives
infra/docker/          Compose stack & Dockerfiles
scripts/               Secret generation & preflight
docs/                  Architecture & product rules
```

## Prerequisites

- Node.js 20+ (22 recommended)
- Python 3.12+ (3.13 works for local install)
- Docker Desktop (recommended for Postgres/pgvector, Redis, MinIO)

## Exact local setup

### 1. Clone and configure environment

```bash
cd ResearchForge
cp .env.example .env
npm run secrets -- --write
npm install
```

### 2. Start infrastructure (Docker)

```bash
npm run docker:up
```

This starts Postgres (pgvector), Redis, MinIO, API, Celery worker, and web.

If Docker is unavailable, run API dependencies yourself and start processes separately (below).

### 3. Backend (without full Compose)

```bash
cd apps/api
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Celery worker (optional locally):

```bash
celery -A app.workers.celery_app:celery_app worker --loglevel=INFO
```

### 4. Frontend

```bash
# from repo root
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API docs: [http://localhost:8000/docs](http://localhost:8000/docs).

## One-command local app (Docker)

```bash
cp .env.example .env
npm run secrets -- --write
npm install
npm run docker:up
```

Then open `http://localhost:3000`.

## Useful commands

| Command                             | Purpose                               |
| ----------------------------------- | ------------------------------------- |
| `npm run dev`                       | Next.js dev server                    |
| `npm run dev:api`                   | FastAPI reload server                 |
| `npm run build`                     | Production builds (workspaces)        |
| `npm run lint`                      | Frontend lint                         |
| `npm run lint:api`                  | Ruff                                  |
| `npm run typecheck`                 | TypeScript                            |
| `npm run test`                      | Frontend + API unit tests             |
| `npm run test:e2e`                  | Playwright smoke                      |
| `npm run db:migrate`                | Alembic upgrade                       |
| `npm run docker:up` / `docker:down` | Compose lifecycle                     |
| `npm run secrets -- --write`        | Generate `SECRET_KEY` / `CSRF_SECRET` |

API-only quality:

```bash
cd apps/api
ruff check app tests
ruff format --check app tests
mypy app
pytest -m "not integration"
pytest -m integration
```

## Health endpoints

- `GET /health/live` — process liveness
- `GET /health/ready` — database, Redis, object storage

## Authentication

See [docs/authentication.md](docs/authentication.md) and [docs/threat-model.md](docs/threat-model.md).

- Argon2id passwords, rotating refresh sessions, CSRF double-submit
- Email verification + password reset (console/fake email providers locally)
- Account settings, active sessions, revoke/delete
- Google OAuth interface documented but disabled without credentials

## Guest workspace rules

- Draft persisted in `localStorage` only (never as guest rows on the server)
- Banner: “This draft is stored only in this browser…”
- Save / Upload / Full Export / Full Similarity Check / Generate Full Section open auth
- After login, confirm conversion once; idempotent via `guest_conversion_key`
- Browser storage cleared only after successful server confirmation

## AI configuration

OpenAI-compatible client; endpoint and model via env:

```env
AI_PROVIDER=openai_compatible
AI_BASE_URL=http://localhost:8001/v1
AI_MODEL_NAME=researchforge-local
```

Tests and offline work:

```env
AI_PROVIDER=fake
```

Optional vLLM notes: [docs/vllm.md](docs/vllm.md).

## Architecture

See [docs/architecture.md](docs/architecture.md), [docs/product-rules.md](docs/product-rules.md), and [docs/export-pipeline.md](docs/export-pipeline.md) for document rendering/export (compatible starting templates only; not publisher-certified).

## Security baseline

- HTTP-only auth cookies + CSRF double-submit scaffolding
- Zod / Pydantic input validation
- Upload size and content-type configuration
- Safe JSON error responses with request IDs
- No secrets in client bundles; `.env` gitignored; `.env.example` committed
