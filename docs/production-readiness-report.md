# Production-readiness report

**Date:** 2026-08-02  
**Product:** ResearchForge

## Architecture

Monorepo SaaS for evidence-grounded research manuscripts:

- **Web:** Next.js (`apps/web`)
- **API:** FastAPI + SQLAlchemy async + Alembic (`apps/api`)
- **Workers:** Celery (default + beat scheduler)
- **Data:** PostgreSQL + pgvector, Redis, S3-compatible object storage
- **Inference:** OpenAI-compatible / vLLM (operator-hosted)
- **Edge:** nginx TLS reverse proxy (example) or Kubernetes Ingress

Private-by-default projects; ownership via `owner_id`. Guests explore only; conversion requires auth.

## Security posture

| Area                                      | Status                                                   |
| ----------------------------------------- | -------------------------------------------------------- |
| Auth (Argon2id, refresh rotation)         | Implemented                                              |
| CSRF double-submit                        | Implemented                                              |
| IDOR / ownership checks                   | Implemented                                              |
| Upload magic-byte + zip safety            | Implemented                                              |
| SSRF guards on LLM/embedding URLs         | Implemented                                              |
| Prompt-injection fencing + citation scrub | Implemented                                              |
| Cross-project retrieval assert            | Implemented                                              |
| Production secret validation              | Implemented                                              |
| Auth abuse rate limits                    | Implemented                                              |
| Redacted structured logs                  | Implemented                                              |
| Threat model documented                   | `docs/threat-model.md`                                   |
| Real malware scanner                      | **Stub** (`fake`/`none`) — launch blocker for high-trust |
| Production email provider                 | **Stub** — launch blocker                                |
| Google OAuth                              | Disabled until configured                                |

## Observability

- Structured JSON logs with redaction
- `GET /metrics` (Prometheus text)
- Tracing hooks (`app.observability.tracing`)
- Error reporter abstraction
- `/health/live` and `/health/ready`
- No manuscript content in telemetry

## Data protection

- TLS / storage encryption guidance, backup/restore, retention, user export (`GET /account/export`), deletion, audit logs, privacy config, inventory — see `docs/data-protection.md`

## Deployment artifacts

- `infra/docker/docker-compose.production.example.yml`
- Hardened Dockerfiles (non-root UID 10001)
- `infra/nginx/researchforge.conf.example`
- `infra/k8s/*` + Helm skeleton
- `docs/deployment.md`, `docs/environment.md`
- Launch checklist: `docs/launch-checklist.md`

## CI/CD

CI includes lint, typecheck, unit/integration tests, Playwright, migration validation, container builds, dependency/secret scanning, SBOM artifacts, staging placeholder, production environment approval gate.

## Test counts (validated locally 2026-08-02)

| Suite                              | Result                                                                                    |
| ---------------------------------- | ----------------------------------------------------------------------------------------- |
| API unit + integration             | **101 passed**                                                                            |
| Web unit (vitest)                  | **8 passed**                                                                              |
| Playwright smoke                   | **2 passed**                                                                              |
| API ruff + mypy                    | clean                                                                                     |
| Prettier format check              | clean                                                                                     |
| Web lint + typecheck               | clean                                                                                     |
| Production Next.js build           | success                                                                                   |
| Alembic head                       | `20260802_0009` (9 revisions)                                                             |
| Docker image builds                | **not run locally** (Docker CLI unavailable on this host; covered in CI `containers` job) |
| Postgres empty-DB migrate/rollback | **CI job `migrations`** (requires pgvector service)                                       |

Failure/load coverage: concurrent autosaves (with conflict recovery), AI/export idempotency, expired session recovery, model unavailable, prompt fencing, account export, metrics.

## Known limitations

1. Malware scanner is not a real AV engine.
2. Email delivery is console/fake until wired.
3. Similarity checker does not guarantee originality.
4. Publisher templates are compatible starting points, not official certification.
5. Postgres `audit_action` enum expansion cannot be downgraded (additive only).
6. Redis is not a durable system of record.

## Deployment procedure (summary)

1. Provision Postgres (pgvector), Redis, S3, TLS proxy, optional GPU vLLM.
2. Set strong secrets (`docs/environment.md`).
3. `alembic upgrade head`
4. Deploy API, workers, scheduler, web.
5. Verify `/health/ready` and launch checklist.

## Required secrets

`SECRET_KEY`, `CSRF_SECRET`, DB credentials, Redis password, S3 keys, `LLM_API_KEY` (as needed), TLS certs. Never commit production values.

## GPU / model requirements

- NVIDIA GPU recommended for local vLLM (profile `gpu` in production compose example).
- OpenAI-compatible HTTP API; model license must be reviewed before launch.
- Embedding endpoint may share or separate from chat model.

## Expected infrastructure components

Web, API, Celery worker, Celery beat, PostgreSQL+pgvector, Redis, S3/MinIO, reverse proxy+TLS, optional vLLM, backup storage, monitoring/alerting.

## Launch blockers

- [ ] Real email provider
- [ ] Real malware scanning (if accepting untrusted binaries at scale)
- [ ] Privacy/Terms/AI/synthetic/similarity/retention disclosures published
- [ ] Backup verification + restore drill
- [ ] Support + abuse + incident response contacts
- [ ] Billing disabled or fully configured
- [ ] Production secrets rotated away from placeholders

## Recommended post-launch priorities

1. Wire production email + abuse mailbox
2. Enable real malware scanning / quarantine workflow
3. OpenTelemetry export to your APM
4. WAL archiving / tighter RPO
5. CSP enforce mode after tuning
6. Licensed similarity provider (optional) with clear UX limitations
7. Harden OAuth and add WebAuthn / SSO as needed
