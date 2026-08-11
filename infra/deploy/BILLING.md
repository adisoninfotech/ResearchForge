# ResearchForge — Billing & Operations Reference

Where to check spend, what the free tiers actually allow, and what is deployed
where. Companion to [DEPLOYMENT.md](./DEPLOYMENT.md).

Deployed: 11 August 2026. All infrastructure in London.

---

## Cost summary

| Service       | Plan          | Cost                |
| ------------- | ------------- | ------------------- |
| Fly.io        | pay-as-you-go | **~£9/month**       |
| GoDaddy       | domain        | **~£15/year**       |
| Cloudflare R2 | Free          | £0                  |
| Supabase      | Free          | £0                  |
| Vercel        | Hobby         | £0                  |
| Groq          | Free          | £0                  |
| **Total**     |               | **~£9/mo + £15/yr** |

Fly is the only service currently charging. It bills monthly in arrears, so the
first invoice arrives at the start of the following month and covers a partial
period.

### Fly breakdown

| App                    | Size                | Approx/month |
| ---------------------- | ------------------- | ------------ |
| `researchforge-api`    | shared-cpu-1x 512MB | $3.19        |
| `researchforge-worker` | shared-cpu-1x 1GB   | $5.70        |
| `researchforge-redis`  | shared-cpu-1x 256MB | $1.94        |
| `redis_data` volume    | 1 GB                | $0.15        |

---

## Billing dashboards

| Service           | URL                                                                          |
| ----------------- | ---------------------------------------------------------------------------- |
| **Fly.io**        | https://fly.io/dashboard/info-adisoninfotech-co-uk/billing                   |
| Fly usage detail  | https://fly.io/dashboard/info-adisoninfotech-co-uk/usage                     |
| **Cloudflare R2** | https://dash.cloudflare.com → Billing (left sidebar)                         |
| **Supabase**      | https://supabase.com/dashboard/project/mgyqcwwkhkhjkzoiddlh/settings/billing |
| **Vercel**        | https://vercel.com/adisoninfotechs-projects/~/settings/billing               |
| **Groq**          | https://console.groq.com/settings/billing                                    |
| **GoDaddy**       | https://account.godaddy.com/products                                         |

Fly usage from the terminal:

```bash
flyctl dashboard metrics
```

---

## Free-tier limits worth watching

### Supabase — projects pause after 7 days idle

The most likely thing to break. A Free-plan project with no activity for a week
is paused automatically: the database stops accepting connections, `/health/ready`
starts reporting `database: error`, and the app is effectively down until you
unpause it by hand from the dashboard.

Mitigations, in order of cost:

- Hit the app at least weekly.
- Add an uptime pinger (UptimeRobot free) against
  `https://www.researchforge.net/health/ready`. Note this only keeps the API warm —
  confirm it actually issues a database query, or it will not prevent the pause.
- Supabase Pro, ~$25/month, no pausing.

Other Free-plan ceilings: 500 MB database, 1 GB file storage, 2 GB egress/month,
2 concurrent connections on the session pooler.

### Vercel Hobby — non-commercial use only

Vercel's terms restrict the Hobby plan to personal, non-commercial projects. The
domain is registered to a business, so if ResearchForge takes payment or is used
commercially, this needs Vercel Pro (~$20/month). This is a licence term, not a
technical limit — nothing will break, but the account is out of compliance.

Hobby also caps at 100 GB bandwidth and 100 GB-hours of function execution per
month.

### Cloudflare R2 — free tier is finite

10 GB storage, 1M Class A operations (writes/lists) and 10M Class B operations
(reads) per month. Uploaded manuscripts accumulate and are never automatically
pruned, so storage is the one that creeps. Check R2 → `researchforge` → Metrics.

Note R2 has no egress fees, which is why it was chosen over S3.

### Groq — rate limited, not billed

Free tier is limited by requests and tokens per minute/day rather than cost.
Under load the API returns 429 and AI jobs fail rather than incurring charges.
Current limits: https://console.groq.com/settings/limits

---

## What is deployed

| Layer     | Location                            | Identifier                          |
| --------- | ----------------------------------- | ----------------------------------- |
| Domain    | GoDaddy → Vercel, SSL auto-renewing | `researchforge.net`                 |
| Canonical | apex 308-redirects to www           | `https://www.researchforge.net`     |
| Frontend  | Vercel `lhr1`                       | project `research-forge-web`        |
| API       | Fly `lhr`                           | `researchforge-api.fly.dev`         |
| Worker    | Fly `lhr`                           | Celery worker + embedded beat       |
| Redis     | Fly `lhr`, private 6PN only         | `researchforge-redis.internal:6379` |
| Database  | Supabase London `eu-west-2`         | project `mgyqcwwkhkhjkzoiddlh`      |
| Storage   | Cloudflare R2, EU jurisdiction      | bucket `researchforge`              |
| LLM       | Groq                                | `llama-3.3-70b-versatile`           |

All regions are deliberately aligned to London — see the Regions section of
DEPLOYMENT.md for why, and what to change if you move.

---

## Cost levers

Ordered by saving, and what each one costs you:

1. **Worker 1 GB → 512 MB**, saves ~$2.50/month. Exports that import pandas,
   scipy, statsmodels and matplotlib together will OOM. `flyctl logs` shows
   `out of memory` when it happens.
2. **API auto-suspend when idle**, saves up to ~$3/month. Set
   `auto_stop_machines = "suspend"` and `min_machines_running = 0` in
   `fly.api.toml`. Costs a ~2s cold start on the first request after idle.
   Note this cannot be applied to the worker or Redis: neither has an HTTP
   service, so Fly has no way to wake them, and the worker must stay running to
   drain the Celery queue.
3. **Collapse to a single machine**, saves ~$5/month. One 1 GB machine running
   redis-server, uvicorn and celery together. Requires adding redis to
   `Dockerfile.api` and a start script, and gives up all isolation — an OOM in
   an export would take the API down with it.

Do not scale `researchforge-worker` above one machine. It runs Celery beat
embedded via `--beat`, so a second instance would fire every scheduled task
twice.

---

## Useful commands

`flyctl` lives at `C:\Users\dilee\.fly\bin\flyctl.exe` and is on PATH in new
terminals.

```bash
# Health of the whole stack in one call
curl https://www.researchforge.net/health/ready

# Machine status
flyctl status --app researchforge-api
flyctl status --app researchforge-worker
flyctl status --app researchforge-redis

# Logs
flyctl logs --app researchforge-api
flyctl logs --app researchforge-worker

# Email verification / password reset links are LOGGED, not sent
# (EMAIL_PROVIDER=console — see Known limitations in DEPLOYMENT.md)
flyctl logs --app researchforge-api | grep -i verif

# List secret names (values are never retrievable)
flyctl secrets list --app researchforge-api

# Restart after a config change
flyctl apps restart researchforge-api
```

---

## Credentials

All deployment credentials are in `C:\Users\dilee\.researchforge-deploy.env` on
the deploying machine. That file is **outside the repository and must never be
committed**. Move it into a password manager and delete the plaintext copy.

Fly secrets are write-only: `flyctl secrets list` shows names and digests but
never values. If the local file is lost, secrets must be regenerated and re-set,
not recovered.
