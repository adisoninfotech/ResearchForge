# Document rendering and export pipeline

ResearchForge renders manuscripts from an internal **canonical manuscript schema** into HTML preview, DOCX, LaTeX, PDF, and packaged ZIPs. Formats are not produced from unrelated code paths.

## Compatible starting templates

Supported templates (not officially certified publisher formats unless separately licensed/approved):

| ID                 | Description                             |
| ------------------ | --------------------------------------- |
| `generic_academic` | Single-column academic manuscript       |
| `ieee_two_column`  | IEEE-style two-column starting template |
| `springer_lncs`    | Springer LNCS-style starting template   |
| `acm`              | ACM-style starting template             |

**Warning shown in every preview/export:** these are compatible starting templates. Authors must verify current journal or conference submission requirements.

## Export outputs

- DOCX
- LaTeX source (`main.tex`)
- PDF (when PDF dependencies are available)
- Overleaf-compatible ZIP (`main.tex`, `references.bib`, `figures/`)
- BibTeX
- Figures ZIP
- Dataset / reproducibility manifest ZIP
- Similarity report PDF (advisory; not a plagiarism guarantee)
- Complete submission package ZIP
- Provenance manifest (JSON)
- Canonical manuscript JSON

## Validation

Before export the pipeline checks missing title/authors, broken citations/cross-references, unverified references, missing figure files/captions, synthetic/simulated disclosures, unresolved similarity findings, and required statements.

- **Warnings** may be acknowledged and included in the job request.
- **Critical** structural failures **block** export (`status=blocked`).

## Provenance manifest

Each export includes machine-readable provenance: project ID, manuscript version, export timestamp, template ID/version, model-generated sections, source documents, dataset/figure provenance, synthetic-data status, analysis run IDs, package versions, and citation verification status.

## Download rules

- Guests cannot download complete manuscripts (`full_export` remains auth-gated).
- Logged-in owners receive short-lived authorized download tokens (`export_download_expire_seconds`, default 900).
- Export jobs are asynchronous (Celery) and retry-safe; tests/local can `process_sync=true`.
- Project purge deletes `projects/{id}/` object storage prefixes, including export artifacts.

## System packages and Docker

Python dependency: `reportlab` (PDF). Optional higher-fidelity HTML→PDF: `weasyprint` plus OS libraries.

Debian/Ubuntu (optional WeasyPrint):

```bash
apt-get install -y libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \
  libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info fonts-liberation
```

The API Dockerfile installs build essentials for the Python stack. Add the WeasyPrint packages above if you enable that engine. Without WeasyPrint, reportlab still produces PDFs.

LaTeX compilation for camera-ready PDFs is **not** performed server-side by default; Overleaf ZIP / local TeX is expected for publisher class files (`IEEEtran`, `llncs`, `acmart`).

## API surface

- `GET /projects/{id}/exports/meta`
- `POST /projects/{id}/exports/preview`
- `POST /projects/{id}/exports/run`
- `GET /projects/{id}/exports/jobs`
- `GET /projects/{id}/exports/jobs/{job_id}`
- `GET /projects/{id}/exports/history`
- `POST /projects/{id}/exports/artifacts/{artifact_id}/download`
- `GET /exports/download/{token}`
