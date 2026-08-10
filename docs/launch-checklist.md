# Launch checklist

Use this before opening ResearchForge to beta or production users.

## Domain and TLS

- [ ] Production domain DNS configured
- [ ] TLS certificates issued and auto-renewing
- [ ] HSTS enabled at reverse proxy
- [ ] `PUBLIC_APP_URL` and CORS origins match production

## Legal / disclosure

- [ ] Privacy policy published and linked
- [ ] Terms of service published and linked
- [ ] AI disclosure: assistive drafting; users remain responsible for accuracy
- [ ] Synthetic-data disclosure: simulated material must be labeled; never presented as collected evidence
- [ ] Similarity-check limitations: no plagiarism guarantee; wording uses “sources checked”
- [ ] Open-source model license review completed for deployed weights
- [ ] Publisher-template disclaimer: compatible starting templates only, not official certification
- [ ] Data-retention disclosure matches configured retention days

## Operations

- [ ] Backup verification succeeded within last 7 days
- [ ] Restore drill completed and documented
- [ ] Monitoring alerts wired (ready, 5xx, AI errors, queue depth)
- [ ] Support email monitored (`SUPPORT_EMAIL` / public contact)
- [ ] Abuse reporting channel documented
- [ ] Incident response runbook reviewed
- [ ] Beta-user feedback channel ready
- [ ] Billing disabled **or** payment provider fully configured (no half-enabled charges)

## Security gate

- [ ] Production secrets are unique (≥32 chars), not `dev-only-*`
- [ ] Real malware scanner enabled if accepting untrusted binaries at scale
- [ ] Production email provider configured
- [ ] Dependency and secret scans clean in CI
- [ ] SBOM artifact retained for the release

## Product language gate

- [ ] UI/docs never claim “zero plagiarism” or plagiarism guarantees
- [ ] Templates never claimed as officially certified by publishers
