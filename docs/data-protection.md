# Data protection

## Encryption in transit

- Terminate TLS at the reverse proxy (nginx / ingress). See `infra/nginx/researchforge.conf.example`.
- Set `COOKIE_SECURE` effectively true in production (`APP_ENV=production` forces secure cookies).
- Configure `S3_USE_SSL=true` and HTTPS endpoints for object storage.
- Internal service mesh TLS is recommended but not required for single-host compose.

## Encryption at rest

| Store          | Guidance                                                                                                       |
| -------------- | -------------------------------------------------------------------------------------------------------------- |
| PostgreSQL     | Enable volume encryption (cloud disk / LUKS). Optional pgcrypto for field-level secrets if required by policy. |
| Redis          | Encrypt volume; do not expose without AUTH; use private network.                                               |
| Object storage | Enable server-side encryption (SSE-S3 / SSE-KMS) on the bucket.                                                |
| Backups        | Encrypt backup artifacts with a key held outside the backup store.                                             |

## Backups

1. **Database**: nightly `pg_dump` (custom format) of the primary; retain per retention policy.
2. **Object storage**: enable versioning + cross-region replication where available.
3. **Redis**: treat as ephemeral cache/queue; rebuild from DB + re-queue jobs after loss.
4. Verify backups weekly (see restore drill in launch checklist).

Commands (example):

```bash
pg_dump -Fc -h $PGHOST -U $PGUSER $PGDATABASE > rf-$(date -u +%Y%m%d).dump
aws s3 cp rf-*.dump s3://$BACKUP_BUCKET/postgres/
```

## Restoration procedure

1. Provision empty Postgres with pgvector extension.
2. `pg_restore -d researchforge rf-YYYYMMDD.dump`
3. Run `alembic upgrade head` only if dump is pre-migration; prefer restoring to matching schema version.
4. Restore object-storage bucket from versioned backup.
5. Point API/workers at restored services; run `/health/ready`.
6. Spot-check: login, open a project, download an export artifact.

## Retention behavior

- Trash retention: `TRASH_RETENTION_DAYS` (default 30).
- Free inactive drafts: `FREE_INACTIVE_DRAFT_DAYS` (default 90).
- User retention actions: Keep / Archive / Export / Delete now (engagement APIs).
- Audit logs retained according to operator policy (recommend ≥ 1 year for security events).

## User export

`GET /api/v1/account/export` returns portable JSON for the authenticated user (account metadata, projects, facts, manuscript text, file metadata). Binary blobs are not inlined. Action is audit-logged as `export_account_data`.

## User deletion

`POST /api/v1/account/delete` with confirmation `DELETE` permanently deletes the account and owned data per cascade rules. Sessions are cleared.

## Audit logs

Security-sensitive actions write `audit_events` rows (login, reset, export, project purge, etc.). Metadata must not include passwords or raw tokens.

## Privacy configuration

- Projects private by default (`is_private=true`).
- `training_opt_in` defaults false.
- Product analytics sanitize properties and never store manuscript content (`docs/engagement.md`).

## Redacted logging

Structlog processor redacts secret-like keys, bearer tokens, emails, and manuscript content keys (`content`, `prompt`, `evidence`, etc.). `AI_LOG_PROMPT_TEXT` must remain false in production.

## Data-processing inventory

| Data category                 | Purpose            | Processors             | Retention                       |
| ----------------------------- | ------------------ | ---------------------- | ------------------------------- |
| Account email / password hash | Auth               | API, Postgres          | Until account deletion          |
| Session tokens (hashed)       | Auth sessions      | API, Postgres          | Session TTL / revoke            |
| Manuscripts / facts           | Product core       | API, workers, Postgres | User retention / delete         |
| Uploaded files                | Evidence           | API, workers, S3       | User retention / delete         |
| Embeddings / chunks           | Retrieval          | API, workers, Postgres | With source file                |
| AI job I/O                    | Assistive drafting | API, workers, LLM host | Job records; prompts not logged |
| Export artifacts              | Download packages  | Workers, S3            | Short-lived signed URLs         |
| Analytics events              | Product metrics    | API, Postgres          | Aggregates; no manuscript text  |
| Audit events                  | Security           | API, Postgres          | Operator policy                 |

No manuscript content is placed in Prometheus metrics, tracing attributes, or analytics payloads.
