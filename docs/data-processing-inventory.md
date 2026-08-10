# Data-processing inventory (summary)

See also [data-protection.md](./data-protection.md).

| #   | System                | Personal data      | Research content             | Third parties         |
| --- | --------------------- | ------------------ | ---------------------------- | --------------------- |
| 1   | Web (Next.js)         | Session cookies    | Editor buffer (browser)      | None by default       |
| 2   | API (FastAPI)         | Email, IP hash, UA | Manuscripts, facts           | Optional OAuth        |
| 3   | Postgres + pgvector   | Accounts, audits   | Chunks, embeddings           | Hosting provider      |
| 4   | Redis                 | Rate-limit keys    | Job IDs only                 | Hosting provider      |
| 5   | S3-compatible storage | None directly      | Uploads, exports             | Storage vendor        |
| 6   | Celery workers        | User IDs           | Processing pipelines         | Same as API           |
| 7   | vLLM / embeddings     | None               | Prompt/evidence at inference | Self-hosted preferred |
| 8   | Email provider        | Email addresses    | Reset/verify links only      | Email vendor          |
| 9   | Error reporter        | Redacted context   | Forbidden                    | Optional Sentry-like  |

Operators must complete DPA / subprocessor lists before EU/UK launch.
