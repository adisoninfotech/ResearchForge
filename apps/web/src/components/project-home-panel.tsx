'use client';

import { Button, Notice } from '@researchforge/ui';
import { useCallback, useEffect, useId, useState } from 'react';
import { api } from '@/lib/api-client';

interface ProjectHomePanelProps {
  projectId: string;
  onCompletionChange?: (percent: number) => void;
}

interface HomePayload {
  completion_percent: number;
  progress: {
    components: Record<
      string,
      { complete: boolean; weight: number; label: string; earned: number }
    >;
    not_word_count_based: boolean;
  };
  completion_change?: { summary?: string; previous_percent?: number; new_percent?: number } | null;
  sections_completed: number;
  sections_total: number;
  missing_evidence: number;
  unsupported_claims: number;
  unverified_references: number;
  dataset_status: string;
  figures_needed: number;
  tables_needed: number;
  similarity_findings: number;
  target_submission_date: string | null;
  last_saved_at: string | null;
  next_recommended_action: string;
  milestones: Array<{ type: string; label: string; achieved: boolean; achieved_at: string | null }>;
  daily_goal: {
    goal_type: string;
    task_sequence: Array<{ id: string; label: string }>;
    completed_step_ids: string[];
    disclaimer: string;
  } | null;
  available_daily_goals: Array<{ type: string; label: string }>;
  unanswered_questions: Array<{
    category: string;
    key: string;
    prompt: string;
    help: string;
    fact_path: string;
  }>;
  retention: {
    message: string;
    retention_policy: string;
    purge_after: string | null;
    trash_at: string | null;
    inactive_draft_days: number | null;
  };
  engagement_principles: Record<string, boolean>;
}

export function ProjectHomePanel({ projectId, onCompletionChange }: ProjectHomePanelProps) {
  const titleId = useId();
  const [home, setHome] = useState<HomePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});
  const [goalType, setGoalType] = useState('complete_a_section');

  const load = useCallback(async () => {
    const data = (await api.engagementHome(projectId)) as unknown as HomePayload;
    setHome(data);
    onCompletionChange?.(data.completion_percent);
  }, [projectId, onCompletionChange]);

  useEffect(() => {
    void load().catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Failed to load project home');
    });
  }, [load]);

  async function setGoal() {
    setBusy(true);
    setError(null);
    try {
      await api.setDailyGoal(projectId, { goal_type: goalType });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not set daily goal');
    } finally {
      setBusy(false);
    }
  }

  async function completeStep(stepId: string) {
    setBusy(true);
    try {
      await api.completeGoalStep(projectId, { step_id: stepId });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update step');
    } finally {
      setBusy(false);
    }
  }

  async function saveAnswer(q: HomePayload['unanswered_questions'][0]) {
    const path = q.fact_path;
    setBusy(true);
    try {
      await api.answerGuidedQuestion(projectId, {
        category: q.category,
        key: q.key,
        value: answerDrafts[path] ?? '',
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save answer');
    } finally {
      setBusy(false);
    }
  }

  async function retention(action: string) {
    if (action === 'delete_now') {
      const typed = window.prompt('Type DELETE to permanently delete this project and its files');
      if (typed !== 'DELETE') return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.retentionAction(projectId, {
        action,
        confirmation: action === 'delete_now' ? 'DELETE' : undefined,
      });
      if (action !== 'delete_now') await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Retention action failed');
    } finally {
      setBusy(false);
    }
  }

  if (!home) {
    return (
      <section
        aria-labelledby={titleId}
        className="rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-4"
      >
        <h2 id={titleId} className="text-lg font-semibold">
          Project home
        </h2>
        <p className="text-sm text-[var(--rf-muted)]">Loading guided progress…</p>
      </section>
    );
  }

  const pct = home.completion_percent;
  const reducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  return (
    <section
      aria-labelledby={titleId}
      className="space-y-4 rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-4"
    >
      <header>
        <h2 id={titleId} className="rf-display text-xl">
          Project home
        </h2>
        <p className="text-xs text-[var(--rf-muted)]">
          Guided progress for genuine research — no manipulative streaks or fake urgency.
        </p>
      </header>

      {error ? <Notice tone="danger">{error}</Notice> : null}

      <div
        role="group"
        aria-label={`Paper completion ${pct} percent. Not based only on word count.`}
      >
        <div className="mb-1 flex justify-between text-sm">
          <span>Paper completion</span>
          <strong>{pct}%</strong>
        </div>
        <div
          className="h-3 w-full overflow-hidden rounded bg-[var(--rf-border)]"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          aria-valuetext={`${pct} percent complete based on research components`}
        >
          <div
            className={`h-full bg-[var(--rf-accent)] ${reducedMotion ? '' : 'transition-[width] duration-500'}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="mt-1 text-xs text-[var(--rf-muted)]">
          Weighted research components (problem, evidence, methods, provenance, integrity) — not
          word count alone.
        </p>
        {home.completion_change?.summary ? (
          <p className="mt-1 text-xs" aria-live="polite">
            Why it changed: {home.completion_change.summary}
            {home.completion_change.previous_percent != null
              ? ` (${home.completion_change.previous_percent}% → ${home.completion_change.new_percent}%)`
              : ''}
          </p>
        ) : null}
      </div>

      <ul className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
        <li>
          Sections: {home.sections_completed}/{home.sections_total}
        </li>
        <li>Missing evidence: {home.missing_evidence}</li>
        <li>Unsupported claims: {home.unsupported_claims}</li>
        <li>Unverified refs: {home.unverified_references}</li>
        <li>Dataset: {home.dataset_status}</li>
        <li>Figures needed: {home.figures_needed}</li>
        <li>Tables needed: {home.tables_needed}</li>
        <li>Similarity open: {home.similarity_findings}</li>
        <li>
          Target date:{' '}
          {home.target_submission_date
            ? new Date(home.target_submission_date).toLocaleDateString()
            : '—'}
        </li>
        <li>
          Last saved: {home.last_saved_at ? new Date(home.last_saved_at).toLocaleString() : '—'}
        </li>
      </ul>

      <Notice tone="info">
        Next recommended action: <strong>{home.next_recommended_action}</strong>
      </Notice>

      <div
        className="space-y-2 rounded border border-[var(--rf-border)] p-3"
        aria-labelledby="retention-heading"
      >
        <h3 id="retention-heading" className="text-sm font-semibold">
          Retention
        </h3>
        <p className="text-xs text-[var(--rf-muted)]">{home.retention.message}</p>
        <p className="text-xs">
          Policy: {home.retention.retention_policy}
          {home.retention.purge_after
            ? ` · Purge after ${new Date(home.retention.purge_after).toLocaleString()}`
            : ''}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button type="button" disabled={busy} onClick={() => void retention('keep')}>
            Keep
          </Button>
          <Button type="button" disabled={busy} onClick={() => void retention('archive')}>
            Archive
          </Button>
          <Button type="button" disabled={busy} onClick={() => void retention('export')}>
            Export
          </Button>
          <Button type="button" disabled={busy} onClick={() => void retention('delete_now')}>
            Delete now
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Daily goal</h3>
        <label className="block text-xs">
          Choose a focus (no time estimates)
          <select
            className="mt-1 w-full rounded border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--rf-accent)]"
            value={goalType}
            onChange={(e) => setGoalType(e.target.value)}
          >
            {home.available_daily_goals.map((g) => (
              <option key={g.type} value={g.type}>
                {g.label}
              </option>
            ))}
          </select>
        </label>
        <Button type="button" disabled={busy} onClick={() => void setGoal()}>
          Set today&apos;s goal
        </Button>
        {home.daily_goal ? (
          <ol className="list-decimal space-y-1 pl-5 text-xs">
            {home.daily_goal.task_sequence.map((step) => {
              const done = home.daily_goal!.completed_step_ids.includes(step.id);
              return (
                <li key={step.id} className="flex items-start justify-between gap-2">
                  <span className={done ? 'line-through opacity-70' : ''}>{step.label}</span>
                  {!done ? (
                    <Button
                      type="button"
                      disabled={busy}
                      onClick={() => void completeStep(step.id)}
                    >
                      Done
                    </Button>
                  ) : (
                    <span className="text-[var(--rf-muted)]">Completed</span>
                  )}
                </li>
              );
            })}
          </ol>
        ) : null}
        {home.daily_goal ? (
          <p className="text-[10px] text-[var(--rf-muted)]">{home.daily_goal.disclaimer}</p>
        ) : null}
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Milestones</h3>
        <ul className="space-y-1 text-xs">
          {home.milestones.map((m) => (
            <li key={m.type} className="flex justify-between gap-2">
              <span>{m.label}</span>
              <span aria-label={m.achieved ? 'Achieved' : 'Not yet'}>{m.achieved ? '✓' : '○'}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Guided questions</h3>
        <p className="text-xs text-[var(--rf-muted)]">
          Answers become structured project facts. AI must not invent missing values.
        </p>
        {home.unanswered_questions.length === 0 ? (
          <p className="text-xs">Key guided questions have answers on file.</p>
        ) : (
          home.unanswered_questions.slice(0, 4).map((q) => (
            <div key={q.fact_path} className="space-y-1">
              <label className="block text-xs font-medium" htmlFor={`gq-${q.fact_path}`}>
                {q.prompt}
              </label>
              <p className="text-[10px] text-[var(--rf-muted)]">{q.help}</p>
              <textarea
                id={`gq-${q.fact_path}`}
                className="w-full rounded border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-1 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--rf-accent)]"
                rows={2}
                value={answerDrafts[q.fact_path] || ''}
                onChange={(e) =>
                  setAnswerDrafts((prev) => ({ ...prev, [q.fact_path]: e.target.value }))
                }
              />
              <Button type="button" disabled={busy} onClick={() => void saveAnswer(q)}>
                Save fact
              </Button>
            </div>
          ))
        )}
      </div>

      <details className="text-xs">
        <summary className="cursor-pointer font-medium focus-visible:outline focus-visible:outline-2">
          Completion components
        </summary>
        <ul className="mt-2 space-y-1">
          {Object.entries(home.progress.components).map(([key, c]) => (
            <li key={key} className="flex justify-between gap-2">
              <span>
                {c.label} ({c.weight}%)
              </span>
              <span>{c.complete ? 'complete' : 'incomplete'}</span>
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
