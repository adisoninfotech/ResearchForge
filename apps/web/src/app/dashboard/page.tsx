'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useMemo, useState } from 'react';
import type { ProjectPublic } from '@researchforge/shared-types';
import { Button, Notice } from '@researchforge/ui';
import { GuestConvertDialog } from '@/components/guest-convert-dialog';
import { useAuth } from '@/components/auth-provider';
import { api } from '@/lib/api-client';
import { isGuestSavePending, loadGuestDraft } from '@/lib/guest-storage';

type Tab = 'active' | 'draft' | 'archived' | 'trash';

const TABS: { id: Tab; label: string; status: string }[] = [
  { id: 'active', label: 'Active', status: 'active' },
  { id: 'draft', label: 'Drafts', status: 'draft' },
  { id: 'archived', label: 'Archived', status: 'archived' },
  { id: 'trash', label: 'Trash', status: 'trash' },
];

function DashboardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading } = useAuth();
  const initialTab = (searchParams.get('status') as Tab) || 'active';
  const [tab, setTab] = useState<Tab>(
    TABS.some((t) => t.id === initialTab) ? initialTab : 'active',
  );
  const [projects, setProjects] = useState<ProjectPublic[]>([]);
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('last_edited');
  const [convertOpen, setConvertOpen] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const statusFilter = useMemo(() => TABS.find((t) => t.id === tab)?.status ?? 'active', [tab]);

  async function reload() {
    const rows = await api.listProjects({ status: statusFilter, q: query || undefined, sort });
    setProjects(rows);
  }

  useEffect(() => {
    if (!loading && !user) router.replace('/login?next=/dashboard');
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    void reload().catch(() => setProjects([]));
    const draft = loadGuestDraft();
    if (isGuestSavePending() || searchParams.get('convert') === '1' || draft.title) {
      if (isGuestSavePending() || searchParams.get('convert') === '1') {
        setConvertOpen(true);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, searchParams, tab, sort]);

  useEffect(() => {
    if (!user) return;
    const handle = setTimeout(() => {
      void reload().catch(() => setProjects([]));
    }, 250);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  if (loading || !user) {
    return <p className="text-sm text-[var(--rf-muted)]">Loading account…</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="rf-display text-3xl">
            Welcome{user.display_name ? `, ${user.display_name}` : ''}
          </h1>
          <p className="text-[var(--rf-muted)]">
            Private research projects with autosave, versions, and retention controls.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => setWizardOpen(true)}>New project</Button>
          <Button variant="secondary" onClick={() => setConvertOpen(true)}>
            Save guest draft
          </Button>
          <Link href="/account">
            <Button variant="ghost">Account</Button>
          </Link>
        </div>
      </div>

      {status ? <Notice>{status}</Notice> : null}

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1 rounded-md border border-[var(--rf-border)] p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`rounded px-3 py-1.5 text-sm ${
                tab === t.id
                  ? 'bg-[var(--rf-accent)] text-[var(--rf-accent-fg)]'
                  : 'text-[var(--rf-muted)] hover:bg-[var(--rf-surface-2)]'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <input
          placeholder="Search title, field, journal…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-11 max-w-xs rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-3 text-sm"
        />
        <select
          className="rounded-md border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-2 text-sm"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
        >
          <option value="last_edited">Last edited</option>
          <option value="title">Title</option>
          <option value="completion">Completion</option>
          <option value="submission_date">Submission date</option>
        </select>
        {tab === 'trash' ? (
          <Button
            variant="danger"
            size="sm"
            onClick={() => {
              if (!confirm('Empty trash permanently? This cannot be undone.')) return;
              void api.emptyTrash().then((r) => {
                setStatus(`Purged ${r.purged} project(s).`);
                void reload();
              });
            }}
          >
            Empty trash
          </Button>
        ) : null}
      </div>

      {projects.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--rf-border)] p-8 text-center">
          <p className="rf-display text-2xl">No projects here yet</p>
          <p className="mt-2 text-sm text-[var(--rf-muted)]">
            Create a research project to open the structured manuscript editor, or convert a guest
            draft after signing in.
          </p>
          <div className="mt-4 flex justify-center gap-2">
            <Button onClick={() => setWizardOpen(true)}>Create project</Button>
            <Button variant="secondary" onClick={() => setConvertOpen(true)}>
              Convert guest draft
            </Button>
          </div>
        </div>
      ) : (
        <ul className="space-y-2">
          {projects.map((project) => (
            <li
              key={project.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-4 py-3"
            >
              <div>
                <Link href={`/projects/${project.id}`} className="font-medium hover:underline">
                  {project.title}
                </Link>
                <p className="text-xs text-[var(--rf-muted)]">
                  {project.target_publisher || project.target_template || 'No journal'} ·{' '}
                  {project.completion_percent}% complete · Last edited{' '}
                  {project.last_activity_at
                    ? new Date(project.last_activity_at).toLocaleString()
                    : '—'}
                  {project.intended_submission_date
                    ? ` · Submit ${project.intended_submission_date}`
                    : ''}
                </p>
                <p className="text-[10px] text-[var(--rf-muted)]">
                  Retention: {project.retention_policy}
                  {project.purge_after
                    ? ` · Permanent deletion after ${new Date(project.purge_after).toLocaleString()}`
                    : ''}
                  {project.legal_hold ? ' · Legal hold' : ''}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {tab !== 'trash' ? (
                  <>
                    <Link href={`/projects/${project.id}`}>
                      <Button size="sm">Open</Button>
                    </Link>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={busyId === project.id}
                      onClick={() => {
                        setBusyId(project.id);
                        void api
                          .trashProject(project.id)
                          .then(() => reload())
                          .finally(() => setBusyId(null));
                      }}
                    >
                      Trash
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      size="sm"
                      onClick={() => {
                        setBusyId(project.id);
                        void api
                          .restoreProject(project.id)
                          .then(() => reload())
                          .finally(() => setBusyId(null));
                      }}
                    >
                      Restore
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => {
                        if (
                          !confirm(
                            `Permanently delete “${project.title}”? Type confirmation will be sent as DELETE.`,
                          )
                        ) {
                          return;
                        }
                        setBusyId(project.id);
                        void api
                          .permanentDelete(project.id)
                          .then(() => {
                            setStatus('Project permanently deleted.');
                            return reload();
                          })
                          .finally(() => setBusyId(null));
                      }}
                    >
                      Delete forever
                    </Button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {wizardOpen ? (
        <CreateProjectWizard
          onClose={() => setWizardOpen(false)}
          onCreated={(p) => {
            setWizardOpen(false);
            router.push(`/projects/${p.id}`);
          }}
        />
      ) : null}

      <GuestConvertDialog
        open={convertOpen}
        onClose={() => setConvertOpen(false)}
        onConverted={(title) => {
          setStatus(`Saved “${title}”.`);
          void reload();
        }}
      />
    </div>
  );
}

function CreateProjectWizard({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (p: ProjectPublic) => void;
}) {
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    title: '',
    research_field: '',
    paper_type: 'empirical',
    target_publisher: '',
    target_template: 'IEEE',
    target_word_count: 6000,
    intended_submission_date: '',
    research_problem: '',
    proposed_contribution: '',
    retention_policy: 'plan_default',
    status: 'draft',
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg space-y-4 rounded-lg border border-[var(--rf-border)] bg-[var(--rf-bg)] p-6 shadow-lg">
        <h2 className="rf-display text-2xl">Create project</h2>
        <p className="text-sm text-[var(--rf-muted)]">Step {step + 1} of 3</p>
        {step === 0 ? (
          <div className="space-y-3">
            <label className="block text-sm">
              Title
              <input
                className="mt-1 h-11 w-full rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-3"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                required
              />
            </label>
            <label className="block text-sm">
              Research field
              <input
                className="mt-1 h-11 w-full rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-3"
                value={form.research_field}
                onChange={(e) => setForm({ ...form, research_field: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              Paper type
              <input
                className="mt-1 h-11 w-full rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-3"
                value={form.paper_type}
                onChange={(e) => setForm({ ...form, paper_type: e.target.value })}
              />
            </label>
          </div>
        ) : null}
        {step === 1 ? (
          <div className="space-y-3">
            <label className="block text-sm">
              Target journal / publisher
              <input
                className="mt-1 h-11 w-full rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-3"
                value={form.target_publisher}
                onChange={(e) => setForm({ ...form, target_publisher: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              Template
              <input
                className="mt-1 h-11 w-full rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-3"
                value={form.target_template}
                onChange={(e) => setForm({ ...form, target_template: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              Target word count
              <input
                className="mt-1 h-11 w-full rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-3"
                type="number"
                value={form.target_word_count}
                onChange={(e) =>
                  setForm({ ...form, target_word_count: Number(e.target.value) || 0 })
                }
              />
            </label>
            <label className="block text-sm">
              Intended submission date
              <input
                className="mt-1 h-11 w-full rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-3"
                type="date"
                value={form.intended_submission_date}
                onChange={(e) => setForm({ ...form, intended_submission_date: e.target.value })}
              />
            </label>
          </div>
        ) : null}
        {step === 2 ? (
          <div className="space-y-3">
            <label className="block text-sm">
              Research problem
              <textarea
                className="mt-1 w-full rounded-md border border-[var(--rf-border)] bg-[var(--rf-bg)] px-3 py-2 text-sm"
                rows={3}
                value={form.research_problem}
                onChange={(e) => setForm({ ...form, research_problem: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              Proposed contribution
              <textarea
                className="mt-1 w-full rounded-md border border-[var(--rf-border)] bg-[var(--rf-bg)] px-3 py-2 text-sm"
                rows={3}
                value={form.proposed_contribution}
                onChange={(e) => setForm({ ...form, proposed_contribution: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              Retention preference
              <select
                className="mt-1 w-full rounded-md border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-2 text-sm"
                value={form.retention_policy}
                onChange={(e) => setForm({ ...form, retention_policy: e.target.value })}
              >
                <option value="plan_default">Plan default</option>
                <option value="keep">Keep (no inactive draft purge)</option>
                <option value="trash_30">Trash retention 30 days</option>
                <option value="inactive_draft_90">Inactive draft 90 days</option>
              </select>
            </label>
            <label className="block text-sm">
              Start as
              <select
                className="mt-1 w-full rounded-md border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-2 text-sm"
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
              >
                <option value="draft">Draft</option>
                <option value="active">Active</option>
              </select>
            </label>
          </div>
        ) : null}
        <div className="flex justify-between gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <div className="flex gap-2">
            {step > 0 ? (
              <Button variant="secondary" onClick={() => setStep((s) => s - 1)}>
                Back
              </Button>
            ) : null}
            {step < 2 ? (
              <Button
                disabled={step === 0 && !form.title.trim()}
                onClick={() => setStep((s) => s + 1)}
              >
                Next
              </Button>
            ) : (
              <Button
                disabled={busy || !form.title.trim()}
                onClick={() => {
                  setBusy(true);
                  void api
                    .createProject({
                      ...form,
                      intended_submission_date: form.intended_submission_date || null,
                    })
                    .then(onCreated)
                    .finally(() => setBusy(false));
                }}
              >
                Create
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<p className="text-sm text-[var(--rf-muted)]">Loading…</p>}>
      <DashboardContent />
    </Suspense>
  );
}
