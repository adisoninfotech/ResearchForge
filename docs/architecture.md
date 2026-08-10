# ResearchForge Architecture

## Overview

ResearchForge is a monorepo SaaS platform for evidence-grounded research manuscript creation.

```
apps/
  web/     Next.js App Router frontend
  api/     FastAPI backend + Celery worker entrypoints
packages/
  shared-types/  Shared TypeScript contracts
  ui/            Reusable accessible UI primitives
infra/docker/    Compose stack & Dockerfiles
```

## Runtime topology (local)

| Service  | Role                                     | Default port |
| -------- | ---------------------------------------- | ------------ |
| web      | Next.js UI                               | 3000         |
| api      | FastAPI HTTP API                         | 8000         |
| worker   | Celery durable jobs                      | —            |
| postgres | PostgreSQL + pgvector                    | 5432         |
| redis    | Cache, rate limits, Celery broker/result | 6379         |
| minio    | S3-compatible object storage             | 9000 / 9001  |

Optional: vLLM profile (see [vllm.md](./vllm.md)).

## Product access model

- **Guests** explore and generate limited previews. Content stays in browser `localStorage`.
- **Guests cannot** persist projects server-side, permanently upload documents, or download complete manuscripts.
- Gated actions (Save, Upload, Full Export, Full Similarity Check, Generate Full Section) open authentication.
- After login, temporary guest drafts can be transferred into a saved project.
- Logged-in users receive autosave, projects, versions, files, datasets, figures, reports, and exports.
- Content is private by default and never used for model training without explicit opt-in.
- Synthetic datasets / simulated results must be visibly labeled.
- Similarity checking never claims a guarantee of zero plagiarism.

## API surface

- Versioned under `/api/v1`
- Health: `/health/live`, `/health/ready` (DB, Redis, object storage)
- OpenAPI at `/docs` and `/openapi.json`
- Auth uses server-side sessions, Argon2id passwords, rotating refresh tokens, and CSRF double-submit (see [authentication.md](./authentication.md))
- Next.js proxies `/api/*` to the API so first-party cookies work with `SameSite=Lax`

## AI integration

Provider-independent orchestration (`LLM_*` / `AI_*` env vars) with:

- OpenAI-compatible / vLLM adapter and deterministic `fake` provider for tests
- Versioned prompt templates in `apps/api/prompts/`
- Celery durable jobs, SSE progress, proposal accept/reject (never silent overwrite)
- Circuit breaker, retries, cancellation, redacted logging

See `docs/vllm.md` for starting vLLM and changing models without code changes.

## Files, references, and evidence

Secure project uploads never trust browser filename/MIME. Flow:

1. Authenticated authorize + ownership check
2. Signature/MIME/size validation, server-controlled object key
3. S3/MinIO store, malware scan adapter, pending → extract → chunk → embed
4. Hybrid lexical+semantic retrieval (pgvector-ready JSON embeddings in tests)
5. References (manual / BibTeX / RIS) with fingerprint dedupe and no invented metadata
6. Evidence links + claim provenance with support warning states

Project purge deletes DB rows (CASCADE) and the `projects/{id}/` object prefix, respecting legal hold and trash retention.

## Dataset Studio

Tabular datasets (CSV/XLSX), deterministic synthetic generation, approved analyses (pandas/NumPy/SciPy/statsmodels/sklearn/matplotlib), figure/table studios, and manuscript inserts with stable IDs. Provenance types distinguish real, public, synthetic, simulated, calculated, and user-entered data. See [dataset-studio.md](./dataset-studio.md).

## Similarity and citation risk

Advisory ensemble overlap review against uploaded/project sources, authorized prior manuscripts, and optional open-license corpus. Never claims zero plagiarism or Turnitin equivalence. See [similarity-checker.md](./similarity-checker.md).

## Document rendering and export

Canonical manuscript schema renders to HTML preview, DOCX, LaTeX, PDF, Overleaf ZIP, BibTeX, figures/dataset packages, similarity report PDF, and a complete submission ZIP. Templates are **compatible starting templates** only (IEEE/ACM/LNCS-style), not official publisher certification. Validation warnings may be acknowledged; critical failures block export. Downloads use short-lived authorized tokens. See [export-pipeline.md](./export-pipeline.md).

## Guided ethical engagement

Weighted completion (not word-count-only), guided fact questions, daily goals without time promises, milestones, user-controlled notifications, retention actions, and privacy-conscious analytics. See [engagement.md](./engagement.md).
