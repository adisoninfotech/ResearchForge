'use client';

import type { Manuscript, ManuscriptSection, ProjectPublic } from '@researchforge/shared-types';
import { Button, Notice } from '@researchforge/ui';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AiAssistantPanel } from '@/components/ai-assistant-panel';
import { CompletenessPanel } from '@/components/completeness-panel';
import { DatasetStudio } from '@/components/dataset-studio';
import { EvidenceWorkspace } from '@/components/evidence-workspace';
import { ExportPanel } from '@/components/export-panel';
import { ProjectHomePanel } from '@/components/project-home-panel';
import { SimilarityPanel } from '@/components/similarity-panel';
import { StructuredEditor } from '@/components/structured-editor';
import { VersionHistory } from '@/components/version-history';
import { useAuth } from '@/components/auth-provider';
import { useAutosave } from '@/lib/autosave';
import { api } from '@/lib/api-client';

const SAVE_LABEL: Record<string, string> = {
  idle: 'Ready',
  saving: 'Saving…',
  saved: 'Saved',
  offline: 'Offline — queued',
  conflict: 'Conflict',
  error: 'Error',
};

export default function ProjectWorkspacePage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const router = useRouter();
  const { user, loading } = useAuth();
  const [project, setProject] = useState<ProjectPublic | null>(null);
  const [manuscript, setManuscript] = useState<Manuscript | null>(null);
  const [activeSectionId, setActiveSectionId] = useState<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [customTitle, setCustomTitle] = useState('');

  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=/projects/${projectId}`);
  }, [loading, user, router, projectId]);

  useEffect(() => {
    if (!user) return;
    void Promise.all([api.getProject(projectId), api.getManuscript(projectId)]).then(([p, m]) => {
      setProject(p);
      setManuscript(m);
      setActiveSectionId(m.sections[0]?.id ?? null);
    });
  }, [user, projectId]);

  const activeSection = useMemo(
    () => manuscript?.sections.find((s) => s.id === activeSectionId) ?? null,
    [manuscript, activeSectionId],
  );

  const onSectionUpdated = useCallback(
    (section: ManuscriptSection, meta?: { completion?: number }) => {
      setManuscript((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          completion_percent: meta?.completion ?? prev.completion_percent,
          sections: prev.sections.map((s) => (s.id === section.id ? section : s)),
          total_word_count: prev.sections
            .map((s) => (s.id === section.id ? section.word_count : s.word_count))
            .reduce((a, b) => a + b, 0),
        };
      });
      setProject((prev) =>
        prev
          ? {
              ...prev,
              completion_percent: meta?.completion ?? prev.completion_percent,
              last_activity_at: new Date().toISOString(),
            }
          : prev,
      );
    },
    [],
  );

  const autosave = useAutosave({
    projectId,
    section: activeSection,
    onSectionUpdated,
  });

  // Save when switching sections
  const selectSection = async (nextId: string) => {
    if (activeSectionId && activeSectionId !== nextId) {
      await autosave.saveNow('section_change');
    }
    setActiveSectionId(nextId);
  };

  if (loading || !user || !project || !manuscript || !activeSection) {
    return <p className="p-8 text-sm text-[var(--rf-muted)]">Loading project workspace…</p>;
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-[var(--rf-muted)]">
            <Link href="/dashboard" className="hover:underline">
              Dashboard
            </Link>{' '}
            / Project
          </p>
          <h1 className="rf-display text-3xl">{project.title}</h1>
          <p className="text-sm text-[var(--rf-muted)]">
            {project.target_publisher || project.target_template || 'No target journal'} ·{' '}
            {manuscript.total_word_count} words · {project.completion_percent}% complete
          </p>
        </div>
        <div className="text-right text-xs text-[var(--rf-muted)]">
          <p>
            Save status:{' '}
            <strong className="text-[var(--rf-fg)]">{SAVE_LABEL[autosave.saveState]}</strong>
          </p>
          <p>
            Last saved:{' '}
            {autosave.lastSavedAt ? new Date(autosave.lastSavedAt).toLocaleString() : '—'}
          </p>
          <p>
            Last activity:{' '}
            {project.last_activity_at ? new Date(project.last_activity_at).toLocaleString() : '—'}
          </p>
          <p>Retention: {project.retention_policy}</p>
          {project.purge_after ? (
            <p className="text-[var(--rf-danger)]">
              Trash expires {new Date(project.purge_after).toLocaleString()}
            </p>
          ) : null}
          {project.legal_hold ? <p>Legal hold active — purge blocked</p> : null}
          <p>
            AI:{' '}
            <button
              type="button"
              className="underline"
              onClick={() => {
                void api
                  .updateProject(projectId, { ai_enabled: !project.ai_enabled })
                  .then(setProject);
              }}
            >
              {project.ai_enabled ? 'enabled' : 'disabled (do not send to AI)'}
            </button>
          </p>
        </div>
      </div>

      {autosave.conflict ? (
        <Notice>
          <div className="space-y-2">
            <p>
              This section changed elsewhere (server revision {autosave.conflict.serverRevision}).
              Your local edits were not applied.
            </p>
            <div className="grid gap-2 md:grid-cols-2">
              <pre className="max-h-40 overflow-auto rounded border border-[var(--rf-border)] p-2 text-xs">
                Server:{'\n'}
                {autosave.conflict.serverPlainText}
              </pre>
              <pre className="max-h-40 overflow-auto rounded border border-[var(--rf-border)] p-2 text-xs">
                Your draft may still be in the editor.
              </pre>
            </div>
            <div className="flex gap-2">
              <Button type="button" onClick={() => autosave.acceptServer()}>
                Use server version
              </Button>
              <Button
                type="button"
                variant="danger"
                onClick={() => void autosave.overwriteServer()}
              >
                Overwrite with mine
              </Button>
            </div>
          </div>
        </Notice>
      ) : null}
      {autosave.errorMessage ? <Notice>{autosave.errorMessage}</Notice> : null}

      <div className="grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)_280px]">
        <nav className="space-y-2" aria-label="Sections">
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--rf-muted)]">
            Sections
          </p>
          <ul className="space-y-1">
            {manuscript.sections.map((section) => (
              <li
                key={section.id}
                draggable
                onDragStart={() => setDragId(section.id)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => {
                  if (!dragId || dragId === section.id) return;
                  const ids = manuscript.sections.map((s) => s.id);
                  const from = ids.indexOf(dragId);
                  const to = ids.indexOf(section.id);
                  if (from < 0 || to < 0) return;
                  ids.splice(to, 0, ids.splice(from, 1)[0]!);
                  void api.reorderSections(projectId, ids).then((res) => {
                    setManuscript((prev) => (prev ? { ...prev, sections: res.sections } : prev));
                  });
                  setDragId(null);
                }}
              >
                <button
                  type="button"
                  onClick={() => void selectSection(section.id)}
                  className={`w-full rounded-md px-2 py-1.5 text-left text-sm ${
                    section.id === activeSectionId
                      ? 'bg-[var(--rf-accent)] text-[var(--rf-accent-fg)]'
                      : 'hover:bg-[var(--rf-surface-2)]'
                  }`}
                >
                  <span className="block truncate">{section.title}</span>
                  <span className="block text-[10px] opacity-80">
                    {section.word_count}w · {section.status}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <form
            className="flex gap-1 pt-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (!customTitle.trim()) return;
              void api.addCustomSection(projectId, customTitle.trim()).then((res) => {
                setManuscript((prev) =>
                  prev ? { ...prev, sections: [...prev.sections, res.section] } : prev,
                );
                setCustomTitle('');
                setActiveSectionId(res.section.id);
              });
            }}
          >
            <input
              className="w-full rounded border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-1 text-xs"
              placeholder="Custom section"
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
            />
            <Button type="submit" size="sm" variant="secondary">
              Add
            </Button>
          </form>
        </nav>

        <main className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="rf-display text-2xl">{activeSection.title}</h2>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => void autosave.saveNow('shortcut')}
              >
                Save (Ctrl/Cmd+S)
              </Button>
            </div>
          </div>
          <StructuredEditor
            section={activeSection}
            disabled={project.status === 'trash'}
            onChange={(structured) => {
              autosave.schedule(structured);
            }}
          />
          <AiAssistantPanel
            projectId={projectId}
            section={activeSection}
            aiEnabled={project.ai_enabled !== false}
            onAccepted={() => {
              void Promise.all([
                autosave.saveNow('after_ai'),
                api.getManuscript(projectId).then(setManuscript),
                api.getProject(projectId).then(setProject),
              ]);
            }}
          />
          <VersionHistory
            projectId={projectId}
            onRestored={(m) => {
              setManuscript(m);
              setActiveSectionId(m.sections[0]?.id ?? null);
            }}
          />
        </main>

        <div className="space-y-4">
          <ProjectHomePanel
            projectId={projectId}
            onCompletionChange={(percent) =>
              setProject((prev) => (prev ? { ...prev, completion_percent: percent } : prev))
            }
          />
          <CompletenessPanel projectId={projectId} />
          <EvidenceWorkspace projectId={projectId} sectionId={activeSectionId} />
          <DatasetStudio projectId={projectId} sectionId={activeSectionId} />
          <SimilarityPanel projectId={projectId} sectionId={activeSectionId} />
          <ExportPanel projectId={projectId} />
        </div>
      </div>
    </div>
  );
}
