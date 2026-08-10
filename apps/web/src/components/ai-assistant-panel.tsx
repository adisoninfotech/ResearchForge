'use client';

import type { AIJob, AIProposal, ManuscriptSection } from '@researchforge/shared-types';
import { Button, Notice } from '@researchforge/ui';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api-client';

interface AiAssistantPanelProps {
  projectId: string;
  section: ManuscriptSection;
  aiEnabled: boolean;
  onAccepted: () => void;
  selectedText?: string;
}

const SECTION_OPS = [
  { id: 'draft_section', label: 'Draft section' },
  { id: 'section_questions', label: 'Suggest questions' },
  { id: 'missing_information', label: 'Missing info' },
  { id: 'generate_abstract', label: 'Generate abstract' },
  { id: 'generate_limitations', label: 'Generate limitations' },
  { id: 'consistency_review', label: 'Consistency review' },
] as const;

const REWRITE_OPS = [
  { id: 'rewrite_clarity', label: 'Rewrite for clarity' },
  { id: 'shorten', label: 'Shorten' },
  { id: 'expand_with_evidence', label: 'Expand with evidence' },
] as const;

export function AiAssistantPanel({
  projectId,
  section,
  aiEnabled,
  onAccepted,
  selectedText = '',
}: AiAssistantPanelProps) {
  const [job, setJob] = useState<AIJob | null>(null);
  const [proposal, setProposal] = useState<AIProposal | null>(null);
  const [evidenceText, setEvidenceText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!job || ['completed', 'failed', 'cancelled'].includes(job.status)) return;
    const timer = setInterval(() => {
      void api.aiJob(job.id).then(setJob);
    }, 800);
    return () => clearInterval(timer);
  }, [job]);

  useEffect(() => {
    if (job?.status === 'completed' && job.proposal_id) {
      void api.aiProposal(job.proposal_id).then(setProposal);
    }
  }, [job]);

  async function run(operation: string) {
    if (!aiEnabled) {
      setError('AI is disabled for this project.');
      return;
    }
    setBusy(true);
    setError(null);
    setProposal(null);
    try {
      const evidence_passages = evidenceText.trim()
        ? [
            {
              id: 'ev-1',
              text: evidenceText.trim(),
              is_synthetic: false,
            },
          ]
        : [];
      const created = await api.aiGenerate({
        operation,
        project_id: projectId,
        section_id: section.id,
        selected_text: selectedText || undefined,
        existing_text: section.plain_text,
        evidence_passages,
        sync: true,
        idempotency_key: `${operation}-${section.id}-${Date.now()}`,
      });
      setJob(created);
      if (created.status === 'failed') {
        setError(created.error_message || 'Generation failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generation failed');
    } finally {
      setBusy(false);
    }
  }

  const warnings =
    (proposal?.model_metadata?.warnings as string[] | undefined) ||
    ((job?.result_payload?.result as { warnings?: string[] } | undefined)?.warnings ?? []);
  const missing =
    (proposal?.model_metadata?.missing_information as string[] | undefined) ||
    ((job?.result_payload?.result as { missing_information?: string[] } | undefined)
      ?.missing_information ??
      []);
  const evidenceUsed =
    (proposal?.model_metadata?.evidence_references as string[] | undefined) ||
    ((job?.result_payload?.result as { evidence_references?: string[] } | undefined)
      ?.evidence_references ??
      []);

  return (
    <section className="space-y-3 rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-4">
      <div>
        <h2 className="rf-display text-xl">AI assist</h2>
        <p className="text-xs text-[var(--rf-muted)]">
          Proposals never overwrite your manuscript until you accept them.
        </p>
      </div>

      {!aiEnabled ? (
        <Notice>AI is disabled for this project (“Do not send this project to AI”).</Notice>
      ) : null}

      <label className="block text-xs">
        Evidence passages (optional)
        <textarea
          className="mt-1 w-full rounded border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-1.5 text-sm"
          rows={3}
          value={evidenceText}
          onChange={(e) => setEvidenceText(e.target.value)}
          placeholder="Paste evidence the model may use. It must not invent citations."
        />
      </label>

      <div className="flex flex-wrap gap-2">
        {SECTION_OPS.map((op) => (
          <Button
            key={op.id}
            size="sm"
            variant="secondary"
            disabled={busy || !aiEnabled}
            onClick={() => void run(op.id)}
          >
            {op.label}
          </Button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {REWRITE_OPS.map((op) => (
          <Button
            key={op.id}
            size="sm"
            variant="ghost"
            disabled={busy || !aiEnabled || !(selectedText || section.plain_text)}
            onClick={() => void run(op.id)}
          >
            {op.label}
          </Button>
        ))}
      </div>

      {job ? (
        <div className="space-y-1 text-xs text-[var(--rf-muted)]">
          <p>
            Status: <strong className="text-[var(--rf-fg)]">{job.status}</strong> · {job.progress}%
          </p>
          {job.model_name ? <p>Model: {job.model_name}</p> : null}
          {job.prompt_template_id ? (
            <p>
              Prompt: {job.prompt_template_id}@{job.prompt_version}
            </p>
          ) : null}
          {busy || job.status === 'running' || job.status === 'queued' ? (
            <Button
              size="sm"
              variant="danger"
              onClick={() => void api.aiCancel(job.id).then(setJob)}
            >
              Cancel generation
            </Button>
          ) : null}
        </div>
      ) : null}

      {error ? <Notice>{error}</Notice> : null}
      {warnings.length ? <Notice>Generated-content warning: {warnings.join(' · ')}</Notice> : null}

      {missing.length ? (
        <div className="text-sm">
          <p className="font-medium">Missing information</p>
          <ul className="list-disc pl-5 text-xs text-[var(--rf-muted)]">
            {missing.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {evidenceUsed.length ? (
        <div className="text-sm">
          <p className="font-medium">Evidence used</p>
          <p className="text-xs text-[var(--rf-muted)]">{evidenceUsed.join(', ')}</p>
        </div>
      ) : null}

      {proposal && proposal.status === 'pending' ? (
        <div className="space-y-2 rounded border border-[var(--rf-border)] p-3">
          <p className="text-sm font-medium">Review AI proposal</p>
          <div className="grid gap-2 md:grid-cols-2">
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded bg-[var(--rf-bg)] p-2 text-xs">
              {proposal.original_text || '(empty)'}
            </pre>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded bg-[var(--rf-bg)] p-2 text-xs">
              {proposal.proposed_text}
            </pre>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              onClick={() => {
                void api.aiAcceptProposal(proposal.id).then(() => {
                  setProposal(null);
                  onAccepted();
                });
              }}
            >
              Accept all
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                const edited = window.prompt('Edit accepted text', proposal.proposed_text);
                if (edited == null) return;
                void api.aiAcceptProposal(proposal.id, edited).then(() => {
                  setProposal(null);
                  onAccepted();
                });
              }}
            >
              Edit & accept
            </Button>
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                void api.aiRejectProposal(proposal.id).then(() => setProposal(null));
              }}
            >
              Reject
            </Button>
          </div>
        </div>
      ) : null}

      {job?.result_payload?.result && !proposal ? (
        <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded border border-[var(--rf-border)] p-2 text-xs">
          {JSON.stringify(job.result_payload.result, null, 2)}
        </pre>
      ) : null}
    </section>
  );
}
