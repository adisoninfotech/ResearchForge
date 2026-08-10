'use client';

import type {
  ClaimProvenancePublic,
  EvidenceLinkPublic,
  EvidencePassage,
  ProjectFilePublic,
  ReferencePublic,
} from '@researchforge/shared-types';
import { Button, Notice } from '@researchforge/ui';
import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api-client';

const RELATIONS = ['supports', 'contradicts', 'background', 'method'] as const;

interface EvidenceWorkspaceProps {
  projectId: string;
  sectionId: string | null;
}

export function EvidenceWorkspace({ projectId, sectionId }: EvidenceWorkspaceProps) {
  const [query, setQuery] = useState('widget latency');
  const [results, setResults] = useState<EvidencePassage[]>([]);
  const [files, setFiles] = useState<ProjectFilePublic[]>([]);
  const [refs, setRefs] = useState<ReferencePublic[]>([]);
  const [links, setLinks] = useState<EvidenceLinkPublic[]>([]);
  const [claims, setClaims] = useState<ClaimProvenancePublic[]>([]);
  const [preview, setPreview] = useState<EvidencePassage | null>(null);
  const [note, setNote] = useState('');
  const [relation, setRelation] = useState<(typeof RELATIONS)[number]>('supports');
  const [importText, setImportText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [fileRows, refRows, linkRows, claimRows] = await Promise.all([
      api.listFiles(projectId),
      api.listReferences(projectId),
      api.listEvidence(projectId, sectionId ?? undefined),
      api.listClaims(projectId, sectionId ?? undefined),
    ]);
    setFiles(fileRows);
    setRefs(refRows);
    setLinks(linkRows);
    setClaims(claimRows);
  }, [projectId, sectionId]);

  useEffect(() => {
    void refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  async function onUpload(fileList: FileList | null) {
    if (!fileList?.length) return;
    setBusy(true);
    setError(null);
    try {
      await api.authorizeUpload(projectId);
      await api.uploadFile(projectId, fileList[0]!);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setBusy(false);
    }
  }

  async function onSearch() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.searchEvidence(projectId, query);
      setResults(res.results);
      setPreview(res.results[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setBusy(false);
    }
  }

  async function onPin() {
    if (!preview) return;
    setBusy(true);
    try {
      await api.pinEvidence(projectId, {
        chunk_id: preview.chunk_id,
        section_id: sectionId,
        relation,
        note: note.trim() || null,
      });
      setNote('');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Pin failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-4 rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-4">
      <div>
        <h2 className="rf-display text-xl">Evidence workspace</h2>
        <p className="text-xs text-[var(--rf-muted)]">
          Search uploads, pin passages, manage references and claim warnings.
        </p>
      </div>
      {error ? <Notice>{error}</Notice> : null}

      <div className="space-y-2">
        <label className="block text-xs font-medium" htmlFor="evidence-upload">
          Upload source
        </label>
        <input
          id="evidence-upload"
          type="file"
          disabled={busy}
          onChange={(e) => void onUpload(e.target.files)}
          className="block w-full text-xs"
        />
        <ul className="space-y-1 text-xs text-[var(--rf-muted)]">
          {files.map((file) => (
            <li key={file.id} className="flex items-center justify-between gap-2">
              <span className="truncate">
                {file.original_filename} · {file.status}
                {file.error_message ? ` — ${file.error_message}` : ''}
              </span>
              <button
                type="button"
                className="underline"
                onClick={() => {
                  void api
                    .patchFile(projectId, file.id, { exclude_from_ai: !file.exclude_from_ai })
                    .then(() => refresh());
                }}
              >
                {file.exclude_from_ai ? 'Include in AI' : 'Exclude from AI'}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex gap-2">
        <input
          className="w-full rounded border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-1 text-sm"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search uploaded references"
        />
        <Button type="button" size="sm" disabled={busy} onClick={() => void onSearch()}>
          Search
        </Button>
      </div>

      {preview ? (
        <div className="space-y-2 border-t border-[var(--rf-border)] pt-3">
          <p className="text-xs text-[var(--rf-muted)]">
            Preview · page {preview.page ?? '—'} · {preview.evidence_key}
          </p>
          <p className="text-sm whitespace-pre-wrap">{preview.text}</p>
          <div className="flex flex-wrap gap-2">
            <select
              className="rounded border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-1 text-xs"
              value={relation}
              onChange={(e) => setRelation(e.target.value as (typeof RELATIONS)[number])}
            >
              {RELATIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
            <input
              className="min-w-[10rem] flex-1 rounded border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-1 text-xs"
              placeholder="Note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
            <Button type="button" size="sm" onClick={() => void onPin()}>
              Pin to section
            </Button>
          </div>
        </div>
      ) : null}

      {results.length > 1 ? (
        <ul className="space-y-1 text-xs">
          {results.map((r) => (
            <li key={r.chunk_id}>
              <button type="button" className="text-left underline" onClick={() => setPreview(r)}>
                {r.text.slice(0, 80)}…
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="space-y-2 border-t border-[var(--rf-border)] pt-3">
        <p className="text-xs font-medium">Pinned evidence</p>
        <ul className="space-y-2 text-xs">
          {links.map((link) => (
            <li key={link.id} className="space-y-1">
              <p>{link.passage?.text?.slice(0, 120) || link.chunk_id}</p>
              <p className="text-[var(--rf-muted)]">
                {link.relation}
                {link.note ? ` · ${link.note}` : ''}
              </p>
              <button
                type="button"
                className="underline"
                onClick={() => {
                  void api.removeEvidence(projectId, link.id).then(() => refresh());
                }}
              >
                Remove evidence
              </button>
            </li>
          ))}
          {!links.length ? (
            <li className="text-[var(--rf-muted)]">No pinned evidence yet.</li>
          ) : null}
        </ul>
      </div>

      <div className="space-y-2 border-t border-[var(--rf-border)] pt-3">
        <p className="text-xs font-medium">References</p>
        <textarea
          className="w-full rounded border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-1 text-xs"
          rows={3}
          placeholder="Paste BibTeX to import"
          value={importText}
          onChange={(e) => setImportText(e.target.value)}
        />
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => {
            void api
              .importReferences(projectId, importText, 'bibtex')
              .then(() => {
                setImportText('');
                return refresh();
              })
              .catch((err: Error) => setError(err.message));
          }}
        >
          Import BibTeX
        </Button>
        <ul className="space-y-1 text-xs">
          {refs.map((ref) => (
            <li key={ref.id}>
              {ref.title || '(missing title)'}
              {ref.year ? ` (${ref.year})` : ''}
              {ref.needs_user_correction ? ' — needs correction' : ''}
            </li>
          ))}
        </ul>
      </div>

      <div className="space-y-2 border-t border-[var(--rf-border)] pt-3">
        <p className="text-xs font-medium">Claim provenance</p>
        <ul className="space-y-2 text-xs">
          {claims.map((claim) => (
            <li key={claim.id}>
              <p>{claim.claim_text}</p>
              <p className="text-[var(--rf-muted)]">
                {claim.support_status} · {claim.user_verification_status}
              </p>
            </li>
          ))}
          {!claims.length ? (
            <li className="text-[var(--rf-muted)]">No AI claims stored for this section.</li>
          ) : null}
        </ul>
      </div>
    </section>
  );
}
