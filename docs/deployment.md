# Production deployment

## Components

| Component    | Role                              |
| ------------ | --------------------------------- |
| `web`        | Next.js frontend                  |
| `api`        | FastAPI                           |
| `worker`     | Celery default queue              |
| `scheduler`  | Celery beat / scheduled retention |
| `postgres`   | PostgreSQL 16 + pgvector          |
| `redis`      | Broker, results, rate limits      |
| `minio` / S3 | Object storage                    |
| `nginx`      | TLS reverse proxy                 |
| `vllm`       | GPU OpenAI-compatible inference   |

Example compose: `infra/docker/docker-compose.production.example.yml`  
Kubernetes sketches: `infra/k8s/`  
Nginx: `infra/nginx/researchforge.conf.example`  
Env reference: `docs/environment.md`

## Docker production builds

```bash
docker build -f infra/docker/Dockerfile.api -t researchforge-api:prod .
docker build -f infra/docker/Dockerfile.web -t researchforge-web:prod .
```

Run API as non-root (production Dockerfile stages). Workers:

```bash
celery -A app.workers.celery_app worker -l info
celery -A app.workers.celery_app beat -l info
```

## Migration procedure

1. Take a DB backup.
2. Deploy API image that includes new Alembic revisions (do not start traffic yet if breaking).
3. `alembic upgrade head`
4. Roll out API/workers/web.
5. Verify `/health/ready` and smoke tests.

## Rollback procedure

1. If migration is backward-compatible: redeploy previous app images.
2. If migration must roll back and `downgrade` is safe: `alembic downgrade -1` then redeploy previous images.
3. Prefer restore-from-backup for destructive migrations.
4. Enum value additions (e.g. `20260802_0009`) are not removable — app rollback without enum downgrade is OK.

## Backup procedure

See [data-protection.md](./data-protection.md). Automate nightly `pg_dump` + object storage replication.

## Disaster recovery notes

- RPO target (suggested): ≤ 24h for MVP; tighten with continuous WAL archiving.
- RTO target (suggested): ≤ 4h for single-region restore.
- Redis loss: restart workers; in-flight jobs may redeliver — jobs are idempotent via keys.
- Object storage loss without backup is catastrophic for uploads/exports — replicate.

## Model-change procedure

1. Deploy new weights to vLLM (new deployment or canary).
2. Update `LLM_MODEL` / `EMBEDDING_MODEL`.
3. Run AI smoke: outline + draft with fake evidence.
4. Watch AI latency/error metrics for 30 minutes.
5. Keep previous model revision for quick rollback.

## Horizontal scaling guidance

| Tier     | Scale                                                                  |
| -------- | ---------------------------------------------------------------------- |
| API      | Stateless; scale replicas behind proxy                                 |
| Workers  | Scale Celery concurrency/replicas by queue depth                       |
| Postgres | Vertical first; read replicas later for analytics                      |
| Redis    | Memory-sized; separate DBs for broker vs cache                         |
| vLLM     | GPU-bound; shard by model or use multiple replicas with sticky routing |
| Web      | CDN + multiple Next.js replicas                                        |

Sticky sessions are not required (JWT/cookie auth is stateless aside from DB session rows).
