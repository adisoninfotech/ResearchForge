# Kubernetes example manifests

Minimal sketches for a production-like ResearchForge deployment. Replace image tags, secrets, and storage classes before use. Prefer Helm for real environments (`infra/helm/researchforge` skeleton).

## Suggested resources

| Manifest                 | Purpose                                      |
| ------------------------ | -------------------------------------------- |
| `namespace.yaml`         | Isolate resources                            |
| `secrets.example.yaml`   | Placeholder secret keys (do not apply as-is) |
| `api-deployment.yaml`    | API Deployment + Service                     |
| `worker-deployment.yaml` | Celery worker                                |
| `web-deployment.yaml`    | Next.js frontend                             |
| `ingress.yaml`           | TLS Ingress                                  |

Postgres, Redis, and object storage are expected as managed services or separate operators (CloudNativePG, Redis Operator, etc.).
