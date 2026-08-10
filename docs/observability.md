# Observability

## Structured logs

- JSON logs outside development (`structlog`).
- Request ID middleware correlation.
- Redaction processor strips secrets and manuscript content keys.

## Metrics

- `GET /metrics` — Prometheus text format.
- Series include AI latency/request counts, upload/export job counters, DB pool gauges.
- **Never** put manuscript text, prompts, or evidence in metric labels/values.

## Tracing hooks

- `app.observability.tracing.span` — lightweight span logging; OpenTelemetry-ready.
- Attribute denylist excludes content fields.

## Error reporting

- `app.observability.errors.LoggingErrorReporter` by default.
- Swap via `set_error_reporter` for Sentry/etc. Ensure PII scrubbing before enablement.

## Health

| Endpoint        | Meaning                     |
| --------------- | --------------------------- |
| `/health/live`  | Process up                  |
| `/health/ready` | DB + Redis + object storage |

## Alerting suggestions

- Ready probe failing > 2 minutes
- AI error rate spike
- Export/upload job failure rate
- DB pool checked-out saturation
- 5xx rate at reverse proxy
