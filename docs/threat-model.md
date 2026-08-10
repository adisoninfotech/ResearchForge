# ResearchForge threat model

## Scope

ResearchForge stores private research manuscripts, uploaded evidence documents, datasets, AI job outputs, and authentication credentials. This threat model covers the API, workers, object storage, model inference path, and web client.

## Assets

| Asset                                     | Sensitivity                        |
| ----------------------------------------- | ---------------------------------- |
| User credentials / sessions               | Critical                           |
| Manuscript content and project facts      | High                               |
| Uploaded documents / datasets             | High                               |
| Export artifacts and signed download URLs | High                               |
| AI prompts, evidence passages, embeddings | High                               |
| Audit logs                                | Medium                             |
| Telemetry / metrics                       | Low (must exclude manuscript text) |

## Adversaries

1. External unauthenticated attacker
2. Authenticated user attacking other tenants (IDOR)
3. Cross-site attacker (CSRF / XSS)
4. Malicious document author (prompt injection, zip bombs, malware)
5. Insider with infra access
6. Compromised dependency / supply chain

## Trust boundaries

```
Browser → TLS reverse proxy → API → PostgreSQL / Redis / S3
API → Celery workers → same data plane
API/workers → vLLM (operator-configured URL only)
Uploaded docs → untrusted evidence → fenced prompts (never tools)
```

The model has **no** filesystem tools, **no** arbitrary network tools, and **no** cross-project retrieval authority. All tool-like operations are server-side APIs with ownership checks.

## Controls by threat class

| Threat                              | Mitigation                                                                                  |
| ----------------------------------- | ------------------------------------------------------------------------------------------- |
| Password theft at rest              | Argon2id hashes; nullable for OAuth-only                                                    |
| Token theft from DB                 | Refresh/verify/reset tokens stored hashed                                                   |
| Session fixation / replay           | Refresh rotation + reuse detection → revoke all                                             |
| CSRF on cookie auth                 | Double-submit CSRF header on mutations                                                      |
| XSS                                 | React escaping; no raw HTML from AI into DOM without sanitization; CSP recommended at proxy |
| SQL injection                       | SQLAlchemy bound parameters; no string-built SQL in app paths                               |
| Object-level auth (IDOR)            | `get_owned_project` / owner_id checks; 404 on miss                                          |
| SSRF                                | Outbound LLM/embedding URLs validated; metadata/link-local blocked in production            |
| Unsafe upload / MIME spoof          | Magic-byte detection; claimed Content-Type ignored for kind                                 |
| Zip bombs / path traversal in OOXML | Entry count, uncompressed size, ratio, and `..` path checks                                 |
| Path traversal in storage keys      | Server-generated object keys; sanitized filenames                                           |
| Rate limiting / brute-force login   | Stricter per-path limits on login/register/password reset                                   |
| Password-reset abuse                | Same generic response; rate limited                                                         |
| Signed URL leakage                  | Short TTL download tokens; no long-lived public buckets                                     |
| Prompt injection via docs           | Untrusted evidence fenced; system rules forbid following evidence instructions              |
| Cross-project retrieval leakage     | Queries filter by `project_id`; defense assert before return                                |
| Sensitive logs                      | Structlog redaction of secrets, emails, manuscript content keys                             |
| Secret management                   | Env/secrets store; production rejects `dev-only-*` placeholders                             |
| Dependency vulnerabilities          | CI dependency scanning + SBOM                                                               |
| Container privileges                | Non-root runtime user in production images; read-only rootfs where feasible                 |
| Account enumeration                 | Forgot-password always returns the same message                                             |
| Guest data leakage                  | No guest manuscript rows; conversion requires auth                                          |
| Training misuse                     | `training_opt_in` defaults false                                                            |
| Citation fabrication                | Server-side evidence ID allowlist scrubbing after model output                              |

## Prompt-injection specific model

| Attack                                 | Expected outcome                                        |
| -------------------------------------- | ------------------------------------------------------- |
| Document says “ignore system prompt”   | Ignored; evidence is data inside fences                 |
| Document asks to reveal other projects | Impossible — retrieval scoped by owner project          |
| Model “requests” filesystem/network    | No tools exposed; orchestration only calls LLM chat API |
| Model invents evidence IDs             | Filtered out against server-supplied IDs                |

## Residual risks / launch blockers awareness

- Malware scanner is currently `fake`/`none` — enable a real scanner before high-trust deployments
- Email provider may be console/fake until a production MTA/API is wired
- Google OAuth exchange remains disabled without credentials
- Similarity checks do **not** guarantee originality or plagiarism absence
- Publisher templates are compatible starting templates, not official certification
- Access JWTs remain valid until expiry after revoke unless session check fails (sessions are checked on each authenticated request)

## Testing expectations

Automated tests cover auth isolation, CSRF, upload signature validation, zip safety, prompt fencing, citation scrubbing, account export/deletion, idempotent jobs, and failure/recoverability scenarios under `apps/api/tests`.
