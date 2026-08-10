# ResearchForge API

FastAPI backend for ResearchForge.

## Local development

```bash
# From repo root
cp .env.example .env
npm run secrets -- --write

cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -e ".[dev]"

# Requires Postgres, Redis, MinIO (via Docker Compose) or local equivalents
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Commands

| Command                                | Purpose         |
| -------------------------------------- | --------------- |
| `npm run lint --prefix apps/api`       | Ruff            |
| `npm run typecheck --prefix apps/api`  | mypy            |
| `npm run test --prefix apps/api`       | pytest          |
| `npm run db:migrate --prefix apps/api` | Alembic upgrade |
