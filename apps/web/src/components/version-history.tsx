'use client';

import type { Manuscript, ManuscriptVersion } from '@researchforge/shared-types';
import { Button } from '@researchforge/ui';
import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api-client';

interface VersionHistoryProps {
  projectId: string;
  onRestored: (manuscript: Manuscript) => void;
}

export function VersionHistory({ projectId, onRestored }: VersionHistoryProps) {
  const [versions, setVersions] = useState<ManuscriptVersion[]>([]);
  const [preview, setPreview] = useState<ManuscriptVersion | null>(null);
  const [compareLeft, setCompareLeft] = useState<string>('');
  const [compareRight, setCompareRight] = useState<string>('');
  const [diff, setDiff] = useState<{ from_text: string; to_text: string } | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setVersions(await api.listVersions(projectId));
  }, [projectId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return (
    <section className="space-y-3 rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="rf-display text-xl">Version history</h2>
          <p className="text-xs text-[var(--rf-muted)]">
            Snapshots for meaningful edits and AI runs. Restore creates a new version.
          </p>
        </div>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!name.trim()) return;
            setBusy(true);
            void api
              .createNamedVersion(projectId, name.trim())
              .then(() => {
                setName('');
                return reload();
              })
              .finally(() => setBusy(false));
          }}
        >
          <input
            className="rounded-md border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-1 text-sm"
            placeholder="Named version"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Button type="submit" disabled={busy || !name.trim()}>
            Save version
          </Button>
        </form>
      </div>

      <ul className="max-h-64 space-y-2 overflow-auto">
        {versions.map((v) => (
          <li
            key={v.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded border border-[var(--rf-border)] px-3 py-2 text-sm"
          >
            <div>
              <p className="font-medium">
                v{v.version_number}
                {v.is_named ? ' · named' : ''} — {v.change_summary}
              </p>
              <p className="text-xs text-[var(--rf-muted)]">
                {new Date(v.created_at).toLocaleString()} · {v.created_by_type}
                {v.model_metadata?.reason ? ` · ${String(v.model_metadata.reason)}` : ''}
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                type="button"
                onClick={() => {
                  void api.getVersion(projectId, v.id).then(setPreview);
                }}
              >
                Preview
              </Button>
              <Button
                variant="secondary"
                type="button"
                disabled={busy}
                onClick={() => {
                  setBusy(true);
                  void api
                    .restoreVersion(projectId, v.id)
                    .then((res) => {
                      onRestored(res.manuscript);
                      return reload();
                    })
                    .finally(() => setBusy(false));
                }}
              >
                Restore
              </Button>
            </div>
          </li>
        ))}
      </ul>

      {preview ? (
        <div className="rounded border border-[var(--rf-border)] p-3 text-sm">
          <p className="font-medium">Preview v{preview.version_number}</p>
          <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs text-[var(--rf-muted)]">
            {(preview.snapshot?.sections || [])
              .map((s) => `# ${s.title}\n${s.plain_text || ''}`)
              .join('\n\n')}
          </pre>
        </div>
      ) : null}

      <div className="space-y-2 border-t border-[var(--rf-border)] pt-3">
        <p className="text-sm font-medium">Compare versions</p>
        <div className="flex flex-wrap gap-2">
          <select
            className="rounded border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-1 text-sm"
            value={compareLeft}
            onChange={(e) => setCompareLeft(e.target.value)}
          >
            <option value="">From…</option>
            {versions.map((v) => (
              <option key={v.id} value={v.id}>
                v{v.version_number}
              </option>
            ))}
          </select>
          <select
            className="rounded border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-1 text-sm"
            value={compareRight}
            onChange={(e) => setCompareRight(e.target.value)}
          >
            <option value="">To…</option>
            {versions.map((v) => (
              <option key={v.id} value={v.id}>
                v{v.version_number}
              </option>
            ))}
          </select>
          <Button
            type="button"
            variant="secondary"
            disabled={!compareLeft || !compareRight}
            onClick={() => {
              void api
                .compareVersions(projectId, compareLeft, compareRight)
                .then((res) => setDiff({ from_text: res.from_text, to_text: res.to_text }));
            }}
          >
            Diff
          </Button>
        </div>
        {diff ? (
          <div className="grid gap-3 md:grid-cols-2">
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded border border-[var(--rf-border)] p-2 text-xs">
              {diff.from_text}
            </pre>
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded border border-[var(--rf-border)] p-2 text-xs">
              {diff.to_text}
            </pre>
          </div>
        ) : null}
      </div>
    </section>
  );
}
