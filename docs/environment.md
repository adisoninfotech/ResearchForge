# Environment variable reference

## Core

| Variable         | Required | Notes                                                |
| ---------------- | -------- | ---------------------------------------------------- |
| `APP_ENV`        | yes      | `development` \| `test` \| `staging` \| `production` |
| `SECRET_KEY`     | yes      | ≥32 chars; production rejects placeholders           |
| `CSRF_SECRET`    | yes      | ≥32 chars; distinct from SECRET_KEY                  |
| `PUBLIC_APP_URL` | yes      | Canonical web origin                                 |
| `CORS_ORIGINS`   | yes      | CSV of allowed origins                               |
| `LOG_LEVEL`      | no       | default `INFO`                                       |
| `API_V1_PREFIX`  | no       | default `/api/v1`                                    |

## Auth / cookies

| Variable                      | Notes                                                  |
| ----------------------------- | ------------------------------------------------------ |
| `COOKIE_SECURE`               | Forced true when `APP_ENV=production`                  |
| `COOKIE_SAMESITE`             | `lax` \| `strict` \| `none`                            |
| `COOKIE_DOMAIN`               | Optional shared parent domain                          |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | default 15                                             |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | default 14                                             |
| `EMAIL_PROVIDER`              | `console` \| `fake` (wire real provider before launch) |
| `GOOGLE_OAUTH_*`              | Optional                                               |

## Data stores

| Variable                          | Notes                          |
| --------------------------------- | ------------------------------ |
| `DATABASE_URL`                    | asyncpg URL                    |
| `DATABASE_URL_SYNC`               | psycopg URL for Alembic/Celery |
| `REDIS_URL`                       | cache / rate limits            |
| `CELERY_BROKER_URL`               | queue broker                   |
| `CELERY_RESULT_BACKEND`           | results                        |
| `S3_ENDPOINT_URL`                 | MinIO/S3                       |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | credentials                    |
| `S3_BUCKET`                       | bucket name                    |
| `S3_USE_SSL`                      | `true` in production           |

## Uploads / exports / AI

| Variable                                 | Notes                                     |
| ---------------------------------------- | ----------------------------------------- |
| `MAX_UPLOAD_BYTES`                       | default ~25MB                             |
| `MALWARE_SCANNER`                        | `fake` \| `none` — replace for production |
| `AI_PROVIDER`                            | `openai_compatible` \| `vllm` \| `fake`   |
| `LLM_BASE_URL`                           | OpenAI-compatible base                    |
| `LLM_API_KEY`                            | Bearer for LLM                            |
| `LLM_MODEL`                              | model id                                  |
| `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` | optional                                  |
| `AI_LOG_PROMPT_TEXT`                     | **must be false in production**           |
| `RATE_LIMIT_ENABLED`                     | default true                              |
| `RATE_LIMIT_DEFAULT`                     | e.g. `100/minute`                         |

## Retention

| Variable                   | Notes      |
| -------------------------- | ---------- |
| `TRASH_RETENTION_DAYS`     | default 30 |
| `FREE_INACTIVE_DRAFT_DAYS` | default 90 |

## Frontend (`apps/web`)

| Variable                 | Notes                                             |
| ------------------------ | ------------------------------------------------- |
| `NEXT_PUBLIC_APP_URL`    | public site URL                                   |
| `NEXT_PUBLIC_API_URL`    | browser-visible API origin (or same-origin proxy) |
| `NEXT_PUBLIC_API_PREFIX` | `/api/v1`                                         |
| `API_PROXY_TARGET`       | server-side proxy target for Next                 |
