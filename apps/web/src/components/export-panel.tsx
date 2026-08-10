'use client';

import type { ManuscriptAuthor } from '@researchforge/shared-types';
import { Button, Notice } from '@researchforge/ui';
import { useCallback, useEffect, useState } from 'react';
import { AuthorsEditor, sanitizeAuthorsForSave } from '@/components/authors-editor';
import { api } from '@/lib/api-client';

interface ExportPanelProps {
  projectId: string;
}

interface TemplateInfo {
  id: string;
  name: string;
  version: string;
  description: string;
  warning: string;
}

interface Artifact {
  id: string;
  kind: string;
  filename: string;
  size_bytes: number;
}

interface ExportJob {
  id: string;
  status: string;
  template_id: string;
  template_warning: string;
  validation_issues: Array<{ code: string; severity: string; message: string }>;
  artifacts: Artifact[];
  error_message?: string | null;
}

export function ExportPanel({ projectId }: ExportPanelProps) {
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [templateId, setTemplateId] = useState('generic_academic');
  const [warning, setWarning] = useState('');
  const [previewHtml, setPreviewHtml] = useState('');
  const [page, setPage] = useState(1);
  const [pageCount, setPageCount] = useState(1);
  const [issues, setIssues] = useState<ExportJob['validation_issues']>([]);
  const [refs, setRefs] = useState<Array<{ order: number; key: string; title?: string }>>([]);
  const [job, setJob] = useState<ExportJob | null>(null);
  const [history, setHistory] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [authors, setAuthors] = useState<ManuscriptAuthor[]>([]);
  const [authorsDirty, setAuthorsDirty] = useState(false);
  const [authorsSaved, setAuthorsSaved] = useState(false);

  const loadMeta = useCallback(async () => {
    const [meta, project] = await Promise.all([
      api.exportMeta(projectId),
      api.getProject(projectId),
    ]);
    setTemplates(meta.templates as TemplateInfo[]);
    setWarning(String(meta.template_warning || ''));
    setAuthors(project.authors?.length ? project.authors : [{ name: '', corresponding: true }]);
    setAuthorsDirty(false);
  }, [projectId]);

  useEffect(() => {
    void loadMeta().catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Failed to load export meta');
    });
  }, [loadMeta]);

  async function saveAuthors(): Promise<ManuscriptAuthor[]> {
    const cleaned = sanitizeAuthorsForSave(authors);
    if (cleaned.length === 0) {
      throw new Error('Add at least one author with a name');
    }
    const updated = await api.updateProject(projectId, { authors: cleaned });
    setAuthors(updated.authors?.length ? updated.authors : cleaned);
    setAuthorsDirty(false);
    setAuthorsSaved(true);
    return updated.authors?.length ? updated.authors : cleaned;
  }

  async function runPreview() {
    setBusy(true);
    setError(null);
    try {
      const exportAuthors = authorsDirty || !authors.some((a) => a.name.trim())
        ? await saveAuthors()
        : sanitizeAuthorsForSave(authors);
      const result = await api.exportPreview(projectId, {
        template_id: templateId,
        page,
        authors: exportAuthors,
        back_matter: {
          funding: 'To be completed',
          conflict_of_interest: 'To be completed',
          data_availability: 'To be completed',
        },
      });
      setPreviewHtml(String(result.html || ''));
      setPageCount(Number(result.page_count || 1));
      setIssues((result.validation_issues as ExportJob['validation_issues']) || []);
      setRefs(
        (result.references_preview as Array<{ order: number; key: string; title?: string }>) || [],
      );
      setWarning(String(result.template_warning || warning));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Preview failed');
    } finally {
      setBusy(false);
    }
  }

  async function runExport() {
    setBusy(true);
    setError(null);
    try {
      const exportAuthors = authorsDirty || !authors.some((a) => a.name.trim())
        ? await saveAuthors()
        : sanitizeAuthorsForSave(authors);
      const warningCodes = issues.filter((i) => i.severity === 'warning').map((i) => i.code);
      const result = (await api.runExport(projectId, {
        template_id: templateId,
        process_sync: true,
        authors: exportAuthors,
        back_matter: {
          funding: 'To be completed',
          conflict_of_interest: 'To be completed',
          data_availability: 'To be completed',
        },
        acknowledged_warnings: warningCodes,
      })) as unknown as ExportJob;
      setJob(result);
      const hist = await api.exportHistory(projectId);
      setHistory((hist.downloads as Array<Record<string, unknown>>) || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setBusy(false);
    }
  }

  async function downloadArtifact(artifactId: string) {
    setBusy(true);
    setError(null);
    try {
      await api.downloadExportArtifact(projectId, artifactId);
      const hist = await api.exportHistory(projectId);
      setHistory((hist.downloads as Array<Record<string, unknown>>) || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed');
    } finally {
      setBusy(false);
    }
  }

  const overflow = issues.filter((i) => i.code.includes('overflow'));

  return (
    <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
      <header>
        <h2 className="text-lg font-semibold text-slate-900">Export &amp; preview</h2>
        <p className="text-sm text-slate-600">
          Render from a canonical manuscript into HTML, DOCX, LaTeX, PDF, and submission packages.
        </p>
      </header>

      {warning ? (
        <Notice tone="warning">
          {warning} ResearchForge does not claim official publisher certification unless officially
          licensed or approved.
        </Notice>
      ) : null}

      {error ? <Notice tone="danger">{error}</Notice> : null}

      <AuthorsEditor
        authors={authors}
        disabled={busy}
        onChange={(next) => {
          setAuthors(next);
          setAuthorsDirty(true);
          setAuthorsSaved(false);
        }}
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant="secondary"
          disabled={busy || !authorsDirty}
          onClick={() => {
            void saveAuthors()
              .then(() => undefined)
              .catch((err: unknown) => {
                setError(err instanceof Error ? err.message : 'Could not save authors');
              });
          }}
        >
          Save authors
        </Button>
        {authorsSaved && !authorsDirty ? (
          <span className="text-xs text-slate-500">Authors saved to project</span>
        ) : null}
      </div>

      <label className="block text-sm text-slate-700">
        Template
        <select
          className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
          value={templateId}
          onChange={(e) => setTemplateId(e.target.value)}
        >
          {templates.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </label>

      <div className="flex flex-wrap gap-2">
        <Button type="button" disabled={busy} onClick={() => void runPreview()}>
          Refresh preview
        </Button>
        <Button type="button" disabled={busy} onClick={() => void runExport()}>
          Run export
        </Button>
        <Button
          type="button"
          disabled={busy || page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          Prev page
        </Button>
        <span className="self-center text-sm text-slate-600">
          Page {page} / {pageCount}
        </span>
        <Button
          type="button"
          disabled={busy || page >= pageCount}
          onClick={() => setPage((p) => p + 1)}
        >
          Next page
        </Button>
      </div>

      {overflow.length > 0 ? (
        <Notice tone="warning">
          Figure/table overflow warnings: {overflow.map((o) => o.message).join(' ')}
        </Notice>
      ) : null}

      {issues.length > 0 ? (
        <div className="max-h-32 overflow-auto text-xs text-slate-700">
          <p className="font-medium">Validation</p>
          <ul className="list-disc pl-4">
            {issues.map((i) => (
              <li key={`${i.code}-${i.message}`}>
                [{i.severity}] {i.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {previewHtml ? (
        <iframe
          title="Manuscript preview"
          className="h-64 w-full rounded border border-slate-200 bg-stone-50"
          srcDoc={previewHtml}
        />
      ) : null}

      {refs.length > 0 ? (
        <div className="text-xs text-slate-700">
          <p className="font-medium">Reference preview</p>
          <ol className="list-decimal pl-4">
            {refs.map((r) => (
              <li key={r.key}>
                [{r.order}] {r.title || r.key}
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {job ? (
        <div className="space-y-2 text-sm">
          <p>
            Export status: <strong>{job.status}</strong>
            {job.error_message ? ` — ${job.error_message}` : ''}
          </p>
          <ul className="space-y-1">
            {job.artifacts.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-2">
                <span>
                  {a.kind} · {a.filename} · {a.size_bytes} bytes
                </span>
                <Button type="button" disabled={busy} onClick={() => void downloadArtifact(a.id)}>
                  Download
                </Button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {history.length > 0 ? (
        <div className="text-xs text-slate-600">
          <p className="font-medium text-slate-800">Download history</p>
          <ul className="list-disc pl-4">
            {history.slice(0, 8).map((h) => (
              <li key={String(h.id)}>
                {String(h.filename || h.artifact_kind)} · expires {String(h.expires_at)}
                {h.expired ? ' (expired)' : ''}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
