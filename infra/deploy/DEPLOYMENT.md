# ResearchForge — Cloud Deployment (always-on)

End-to-end recipe for putting ResearchForge on managed infrastructure with no
application code changes. Every provider swap is configuration only.

| Piece | Provider | Cost |
| --- | --- | --- |
| Next.js frontend | Vercel (Hobby) | free |
| FastAPI API | Fly.io, 512 MB | ~$2–4/mo |
| Celery worker + beat | Fly.io, 1 GB | ~$5–6/mo |
| Redis (cache + broker) | Fly.io, 256 MB + 1 GB volume | ~$2/mo |
| Postgres + pgvector | Supabase (Free) | free |
| Object storage | Cloudflare R2 (Free) | free |
| LLM inference | Groq (Free) | free |

**Honest total: roughly $9–12/month, not $0.** The three Fly machines are the
reason — see [Why it is not free](#why-it-is-not-free) for what actually forces
that, and the cheaper trade-offs if you want the bill closer to zero.

First run takes 60–90 minutes, most of it waiting on provider provisioning.

---

## Files in this bundle

```
.dockerignore                          # repo root — trims the shared build context
infra/deploy/
├── DEPLOYMENT.md                      # this file
├── .env.example.free-cloud            # every variable, annotated, grouped by provider
└── fly/
    ├── fly.api.toml                   # API app
    ├── fly.worker.toml                # Celery worker + embedded beat
    └── fly.redis.toml                 # private Redis
apps/web/vercel.json                   # Vercel project config
```

There is no new Dockerfile. Fly reuses the existing `infra/docker/Dockerfile.api`
so the deployed image cannot drift from the one you test locally with
`npm run docker:up`.

---

## Prerequisites

```bash
# Fly CLI
curl -L https://fly.io/install.sh | sh      # macOS/Linux
iwr https://fly.io/install.ps1 -useb | iex  # Windows PowerShell
fly auth signup

# Vercel CLI (optional — the dashboard works too)
npm i -g vercel && vercel login
```

Accounts needed: Fly.io (credit card required even on small machines),
Supabase, Cloudflare, Groq, Vercel.

Generate the two signing secrets now, you will need them in step 4:

```bash
npm run secrets
```

---

## Regions — set these consistently

This deployment targets the **UK**. Every provider is pinned to London, and they
must stay in agreement — a Supabase project in Virginia behind a Fly app in
London adds a round-trip to *every* query, and this app is chatty with the
database.

| Provider | Region | Set where |
| --- | --- | --- |
| Fly (api, worker, redis) | `lhr` | `primary_region` in each `fly.*.toml` |
| Supabase | West EU (London) `eu-west-2` | project creation form — **cannot be changed later** |
| Vercel | `lhr1` | `apps/web/vercel.json` |
| Cloudflare R2 | jurisdiction: European Union | bucket creation form |

R2 is the odd one out: it has no regions, so `S3_REGION=auto` regardless. What
it does have is an optional **jurisdiction** setting that constrains where
objects physically live. Choose it at bucket creation — it cannot be changed
afterwards, and uploaded manuscripts are the most sensitive data here.

To deploy elsewhere, change all four together.

## Step 1 — Supabase (Postgres + pgvector)

1. Create a project. Region **West EU (London)**. Save the database password;
   it is shown once.
2. **Database → Extensions**: enable `vector` and `uuid-ossp`.
   The initial migration (`apps/api/alembic/versions/20260322_0001_initial.py`)
   issues `CREATE EXTENSION IF NOT EXISTS` for both, but Supabase restricts
   extension creation on some plans, so enabling them by hand first avoids a
   failed release command.
3. **Connect → Session pooler**: copy that URI. It looks like
   `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`.
4. Rewrite the scheme to `postgresql+asyncpg://`.

### Database URLs — read this before picking a connection string

Two things about this repo drive the choice:

- **Alembic connects asynchronously.** `apps/api/alembic/env.py:74` sets
  `sqlalchemy.url` from `settings.database_url` and runs
  `async_engine_from_config`. Migrations use asyncpg, the same as the app.
  `DATABASE_URL_SYNC` exists in `config.py` but nothing reads it — so there is
  **one** connection string to get right, not two.
- **The engine takes no `connect_args`.** `apps/api/app/db/session.py:17` builds
  `create_async_engine(url, pool_pre_ping=True)` with nothing else. There is no
  place to disable asyncpg's prepared-statement cache without editing code.

So: use the **session pooler on port 5432**. The transaction pooler (6543)
breaks asyncpg's prepared statements, and the direct `db.<ref>.supabase.co`
host is IPv6-only on new projects.

---

## Step 2 — Cloudflare R2 (object storage)

1. **R2 → Create bucket**, name it `researchforge`. Under Location choose
   **Specify jurisdiction → European Union** (permanent; see Regions above).
2. **Manage R2 API Tokens → Create token**, Object Read & Write, scoped to that
   bucket. Save the access key ID and secret — the secret is shown once.
3. Note your account ID from the R2 overview page. The endpoint for an
   EU-jurisdiction bucket carries an `.eu` segment:
   `https://<account-id>.eu.r2.cloudflarestorage.com`

   Using the plain `https://<account-id>.r2.cloudflarestorage.com` form against
   an EU bucket fails with a "bucket does not exist" error that reads like a
   naming mistake. The token result screen prints the correct endpoint — copy it
   from there.

`S3_REGION` must be the literal string `auto`; R2 has no regions. It is already
set in `fly.api.toml`/`fly.worker.toml`, so you do not pass it as a secret.

The app talks to R2 through boto3 with a custom `endpoint_url`
(`apps/api/app/services/storage.py:51`), which is exactly the MinIO code path —
nothing changes.

---

## Step 3 — Groq (LLM)

Create an API key at <https://console.groq.com/keys>.

`AI_PROVIDER` stays `openai_compatible`. `config.py:118-142` already aliases
`AI_BASE_URL`, `AI_API_KEY` and `AI_MODEL_NAME` onto the internal `llm_*`
settings, so pointing at `https://api.groq.com/openai/v1` is the whole change.

Groq serves no embeddings endpoint. Leave `EMBEDDING_BASE_URL` unset — see
[Known limitations](#known-limitations) for what that costs you.

---

## Step 4 — Fly: Redis

Redis first, because the API and worker need its hostname.

```bash
fly launch --no-deploy --copy-config --config infra/deploy/fly/fly.redis.toml
fly volumes create redis_data --app researchforge-redis --region lhr --size 1
fly secrets set --app researchforge-redis REDIS_PASSWORD="$(openssl rand -hex 24)"
fly deploy --config infra/deploy/fly/fly.redis.toml
```

Save that password. Do **not** allocate a public IP — the app reaches it over
Fly's private network at `researchforge-redis.internal`.

---

## Step 5 — Fly: API

All commands run **from the repo root** so the Docker build context is the root
(the Dockerfile copies `apps/api/...` paths).

```bash
fly launch --no-deploy --copy-config \
  --config infra/deploy/fly/fly.api.toml \
  --dockerfile infra/docker/Dockerfile.api
```

Set secrets — fill in the placeholders from steps 1–4:

```bash
fly secrets set --app researchforge-api \
  SECRET_KEY="<from npm run secrets>" \
  CSRF_SECRET="<from npm run secrets>" \
  DATABASE_URL="postgresql+asyncpg://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:5432/postgres" \
  REDIS_URL="redis://default:<redis-pw>@researchforge-redis.internal:6379/0" \
  CELERY_BROKER_URL="redis://default:<redis-pw>@researchforge-redis.internal:6379/1" \
  CELERY_RESULT_BACKEND="redis://default:<redis-pw>@researchforge-redis.internal:6379/2" \
  S3_ENDPOINT_URL="https://<account-id>.eu.r2.cloudflarestorage.com" \
  S3_ACCESS_KEY="<r2-key-id>" \
  S3_SECRET_KEY="<r2-secret>" \
  S3_BUCKET="researchforge" \
  AI_PROVIDER="openai_compatible" \
  AI_BASE_URL="https://api.groq.com/openai/v1" \
  AI_API_KEY="<groq-key>" \
  AI_MODEL_NAME="llama-3.3-70b-versatile" \
  EMAIL_PROVIDER="console" \
  PUBLIC_APP_URL="https://<placeholder>.vercel.app" \
  CORS_ORIGINS="https://<placeholder>.vercel.app"
```

`PUBLIC_APP_URL` and `CORS_ORIGINS` are placeholders for now; step 7 corrects
them once Vercel has assigned the real domain.

```bash
fly deploy --config infra/deploy/fly/fly.api.toml \
           --dockerfile infra/docker/Dockerfile.api
```

The `[deploy] release_command = "alembic upgrade head"` runs migrations on a
temporary machine before the new version takes traffic. If it fails, the deploy
aborts and the old version keeps serving.

Verify:

```bash
curl https://researchforge-api.fly.dev/health/live    # process is up
curl https://researchforge-api.fly.dev/health/ready   # Postgres + Redis + R2
```

`/health/ready` is the one that proves all three of your Supabase, Redis and R2
wirings at once. **Read the JSON body, not the status code** — the endpoint
returns HTTP 200 either way and reports per-component state
(`apps/api/app/api/health.py:41-59`):

```json
{"status":"ok","components":[
  {"name":"database","status":"ok"},
  {"name":"redis","status":"ok"},
  {"name":"object_storage","status":"ok"}]}
```

Any `"status":"error"` component names exactly which provider is misconfigured.
Fly's own healthcheck deliberately uses `/health/live` only, so a transient
provider blip cannot trigger a restart loop.

---

## Step 6 — Fly: Celery worker

```bash
fly launch --no-deploy --copy-config \
  --config infra/deploy/fly/fly.worker.toml \
  --dockerfile infra/docker/Dockerfile.api
```

The worker needs the same secrets as the API. Copy them across:

```bash
fly secrets set --app researchforge-worker \
  SECRET_KEY="..." CSRF_SECRET="..." DATABASE_URL="..." \
  REDIS_URL="..." CELERY_BROKER_URL="..." CELERY_RESULT_BACKEND="..." \
  S3_ENDPOINT_URL="..." S3_ACCESS_KEY="..." S3_SECRET_KEY="..." S3_BUCKET="researchforge" \
  AI_PROVIDER="openai_compatible" AI_BASE_URL="https://api.groq.com/openai/v1" \
  AI_API_KEY="..." AI_MODEL_NAME="llama-3.3-70b-versatile" \
  EMAIL_PROVIDER="console" PUBLIC_APP_URL="..." CORS_ORIGINS="..."

fly deploy --config infra/deploy/fly/fly.worker.toml \
           --dockerfile infra/docker/Dockerfile.api
```

Confirm the worker registered its queues and the two scheduled jobs from
`app/workers/celery_app.py`:

```bash
fly logs --app researchforge-worker
# expect: "celery@... ready." and beat entries for
# project-retention-cleanup-hourly / pending-deletion-notices-daily
```

**Keep this app at exactly one machine.** It runs beat embedded via `--beat`;
scaling to two would fire every scheduled task twice.

---

## Step 7 — Vercel: frontend

Import the repo, then in **Project Settings**:

- **Root Directory**: `apps/web`
- Leave "Include source files outside of the Root Directory" **on** — the build
  needs `packages/ui` and `packages/shared-types`, which
  `next.config.ts` lists under `transpilePackages`.
- Framework preset: Next.js (also pinned in `apps/web/vercel.json`).

Environment variables (Production):

| Variable | Value |
| --- | --- |
| `API_PROXY_TARGET` | `https://researchforge-api.fly.dev` |
| `NEXT_PUBLIC_APP_URL` | `https://<your-project>.vercel.app` |
| `NEXT_PUBLIC_API_URL` | `https://<your-project>.vercel.app` |
| `NEXT_PUBLIC_API_PREFIX` | `/api/v1` |

`NEXT_PUBLIC_API_URL` pointing at Vercel rather than Fly is not a mistake. The
rewrites in `next.config.ts:10-21` forward `/api/*` and `/health/*` to
`API_PROXY_TARGET` server-side, so the browser only ever issues same-origin
requests and the auth cookies stay first-party. That is why `COOKIE_DOMAIN` must
stay empty.

Deploy, then point the API at the real domain:

```bash
fly secrets set --app researchforge-api \
  PUBLIC_APP_URL="https://<your-project>.vercel.app" \
  CORS_ORIGINS="https://<your-project>.vercel.app"
fly secrets set --app researchforge-worker \
  PUBLIC_APP_URL="https://<your-project>.vercel.app" \
  CORS_ORIGINS="https://<your-project>.vercel.app"
```

Each `fly secrets set` restarts the app. Give it ~30 seconds, then load the site
and register an account.

---

## Smoke test

1. `curl https://<project>.vercel.app/health/ready` → proves the Vercel→Fly
   proxy works, not just Fly directly. All three components should read `"ok"`.
2. Register a user. The verification link is **logged, not emailed**
   (`EMAIL_PROVIDER=console`) — retrieve it with
   `fly logs --app researchforge-api`.
3. Create a project, upload a PDF → exercises R2 writes.
4. Generate an outline → exercises Groq.
5. Run an export → exercises the Celery worker end to end. Watch it with
   `fly logs --app researchforge-worker`.

---

## Why it is not free

Fly's free allowance covers three 256 MB shared-cpu-1x machines. This stack does
not fit in 256 MB:

- The API image installs pandas, numpy, scipy, statsmodels, scikit-learn,
  matplotlib and reportlab (`apps/api/pyproject.toml:34-40`). Importing that set
  alone is several hundred MB of resident memory before serving a request.
- The worker runs the export and analysis tasks that actually exercise those
  libraries, so it needs the most headroom of the three.

Ways to cut the bill if you want:

- **Set `auto_stop_machines = "suspend"` and `min_machines_running = 0`** in
  `fly.api.toml`. Costs you a cold start on the first request after idle, saves
  most of the API's cost. Not appropriate if reviewers are hitting the demo
  cold.
- **Drop the worker to 512 MB** if you never run large exports. It will OOM on
  the heavy ones; `fly logs` shows `out of memory` when it happens.
- **Use Upstash for `REDIS_URL` only** and skip the Redis machine — but then you
  have nowhere to put the Celery broker, so this only works if you also drop the
  worker, which disables exports and scheduled cleanup.

---

## Known limitations of this configuration

**Embeddings are hash-based, not semantic.**
`apps/api/app/services/files/embeddings.py:56-61` falls back to
`FakeEmbeddingProvider` — a deterministic 64-dimension hash — whenever
`EMBEDDING_BASE_URL` is empty. Groq has no embeddings endpoint, so it stays
empty. Retrieval and citation grounding still function, but ranking quality is
substantially worse than with real embeddings. To fix, point
`EMBEDDING_BASE_URL` at any OpenAI-compatible embeddings service and set
`EMBEDDING_MODEL` to match.

No schema migration is needed to switch later: vectors are stored as JSONB with
a per-row `dimensions` column (`app/models/project_file.py:220-224`), not a
fixed-width pgvector column. But existing chunks keep their old 64-dim hash
vectors, so you must re-embed already-uploaded files or their scores will be
meaningless alongside new ones.

**No real email delivery.** `config.py:55` restricts `email_provider` to
`console` or `fake`. Verification and password-reset links must be read from
`fly logs`. Anything more requires adding a provider to the enum and an
implementation behind it.

**Beat runs inside the single worker.** Fine at one machine, wrong at two.

---

## Troubleshooting

**Release command fails: `prepared statement "__asyncpg_stmt_1__" already exists`**
You are on the transaction pooler (port 6543). Switch `DATABASE_URL` to the
session pooler on 5432. See [Database URLs](#database-urls--read-this-before-picking-a-connection-string).

**Release command fails: `type "vector" does not exist`**
The `vector` extension was not enabled in Supabase. Enable it under
Database → Extensions and redeploy.

**`/health/ready` reports `degraded` or `error` in its body**
The `components` array names the failing dependency. `database` → check the
Supabase URL and driver prefix. `redis` → check the password matches and the
host is `researchforge-redis.internal` (`.internal`, not `.fly.dev`).
`object_storage` → check the R2 keys and that the bucket exists. The most common
cause is a missing `.eu` in `S3_ENDPOINT_URL` for an EU-jurisdiction bucket,
which surfaces as "bucket does not exist" rather than as a routing error.

**Worker starts but no task ever runs**
The API and worker are on different broker URLs. They must match exactly,
including the `/1` database index.

**Frontend loads, every API call 404s**
`API_PROXY_TARGET` is unset or has a trailing slash on Vercel. It must be
`https://researchforge-api.fly.dev` with no trailing slash. Redeploy after
changing it — Next.js reads it at build time in `next.config.ts:3`.

**Login succeeds but the next request is unauthenticated**
Something is bypassing the proxy. Check `NEXT_PUBLIC_API_URL` is the Vercel
origin, not the Fly one, and that `COOKIE_DOMAIN` is unset on Fly.

**Export downloads fail with a CORS error in the browser console**
Presigned R2 URLs are being fetched by JavaScript rather than navigated to. Add
a CORS rule on the R2 bucket allowing `GET` from your Vercel origin.

**Worker dies mid-export, logs show `out of memory`**
Raise `memory` in `fly.worker.toml` and redeploy.

---

## Redeploying

```bash
# API (runs migrations first)
fly deploy --config infra/deploy/fly/fly.api.toml --dockerfile infra/docker/Dockerfile.api

# Worker
fly deploy --config infra/deploy/fly/fly.worker.toml --dockerfile infra/docker/Dockerfile.api
```

Frontend redeploys automatically on push to the default branch.

Deploy the API before the worker when a change includes a migration — the API's
release command is the only thing that runs `alembic upgrade head`.
