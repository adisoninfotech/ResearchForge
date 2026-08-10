'use client';

import { GUEST_STORAGE_MESSAGE, type GuestDraft } from '@researchforge/shared-types';
import { Button, Input, Notice, Textarea } from '@researchforge/ui';
import { useMutation } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api-client';
import {
  clearGuestDraft,
  emptyGuestDraft,
  loadGuestDraft,
  markGuestSavePending,
  saveGuestDraft,
} from '@/lib/guest-storage';
import { useAuth } from './auth-provider';
import { AuthGateDialog } from './auth-gate-dialog';
import { GuestConvertDialog } from './guest-convert-dialog';
import { SectionEditor } from './section-editor';

type GateAction =
  'Save' | 'Upload' | 'Full Export' | 'Full Similarity Check' | 'Generate Full Section';

export function GuestWorkspace() {
  const router = useRouter();
  const { user } = useAuth();
  const [draft, setDraft] = useState<GuestDraft>(emptyGuestDraft);
  const [hydrated, setHydrated] = useState(false);
  const [gateOpen, setGateOpen] = useState(false);
  const [gateAction, setGateAction] = useState<GateAction>('Save');
  const [convertOpen, setConvertOpen] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    setDraft(loadGuestDraft());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveGuestDraft(draft);
  }, [draft, hydrated]);

  const outlineMutation = useMutation({
    mutationFn: () =>
      api.guestOutline({
        title: draft.title,
        research_area: draft.researchArea,
        target_format: draft.targetFormat,
        research_problem: draft.researchProblem,
        proposed_contribution: draft.proposedContribution,
      }),
    onSuccess: (data) => {
      setDraft((prev) => ({
        ...prev,
        outline: data.outline.sections,
      }));
      setStatus(data.outline.disclaimer);
    },
    onError: (error: Error) => {
      setStatus(error.message);
    },
  });

  function openGate(action: GateAction) {
    if (action === 'Save' && user) {
      markGuestSavePending();
      setConvertOpen(true);
      return;
    }
    if (action === 'Save') {
      markGuestSavePending();
    }
    setGateAction(action);
    setGateOpen(true);
  }

  function update<K extends keyof GuestDraft>(key: K, value: GuestDraft[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  if (!hydrated) {
    return <p className="text-sm text-[var(--rf-muted)]">Loading workspace…</p>;
  }

  return (
    <div className="space-y-6">
      <Notice>{GUEST_STORAGE_MESSAGE}</Notice>

      <div className="grid gap-4 md:grid-cols-2">
        <Input
          label="Paper title"
          name="title"
          value={draft.title}
          onChange={(e) => update('title', e.target.value)}
          placeholder="Evidence-grounded drafting for scholarly writing"
        />
        <Input
          label="Research area"
          name="researchArea"
          value={draft.researchArea}
          onChange={(e) => update('researchArea', e.target.value)}
          placeholder="Natural language processing"
        />
        <label className="flex w-full flex-col gap-1.5 text-sm md:col-span-2">
          <span className="font-medium">Target format</span>
          <select
            className="h-11 rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-3"
            value={draft.targetFormat}
            onChange={(e) => update('targetFormat', e.target.value)}
          >
            <option value="IEEE">IEEE</option>
            <option value="ACM">ACM</option>
            <option value="APA">APA</option>
            <option value="Nature">Nature</option>
            <option value="Custom">Custom</option>
          </select>
        </label>
        <Textarea
          label="Research problem"
          name="researchProblem"
          value={draft.researchProblem}
          onChange={(e) => update('researchProblem', e.target.value)}
          className="md:col-span-2"
        />
        <Textarea
          label="Proposed contribution"
          name="proposedContribution"
          value={draft.proposedContribution}
          onChange={(e) => update('proposedContribution', e.target.value)}
          className="md:col-span-2"
        />
      </div>

      <div className="flex flex-wrap gap-3">
        <Button
          onClick={() => outlineMutation.mutate()}
          disabled={outlineMutation.isPending || !draft.title || !draft.researchArea}
        >
          {outlineMutation.isPending ? 'Generating…' : 'Generate Outline'}
        </Button>
        <Button variant="secondary" onClick={() => openGate('Save')}>
          Save
        </Button>
        <Button variant="ghost" onClick={() => openGate('Upload')}>
          Upload
        </Button>
        <Button variant="ghost" onClick={() => openGate('Full Export')}>
          Full Export
        </Button>
        <Button variant="ghost" onClick={() => openGate('Full Similarity Check')}>
          Full Similarity Check
        </Button>
        <Button variant="ghost" onClick={() => openGate('Generate Full Section')}>
          Generate Full Section
        </Button>
        <Button
          variant="danger"
          onClick={() => {
            clearGuestDraft();
            setDraft(emptyGuestDraft());
            setStatus('Temporary draft cleared from this browser.');
          }}
        >
          Clear temporary draft
        </Button>
      </div>

      {status ? <p className="text-sm text-[var(--rf-muted)]">{status}</p> : null}

      {draft.outline.length > 0 ? (
        <section aria-labelledby="outline-heading" className="space-y-3">
          <h2 id="outline-heading" className="rf-display text-2xl">
            Preview outline
          </h2>
          <ol className="space-y-2">
            {draft.outline.map((section) => (
              <li
                key={section.title}
                className="rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-3 py-2"
              >
                <p className="font-medium">{section.title}</p>
                <p className="text-sm text-[var(--rf-muted)]">{section.summary}</p>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <section aria-labelledby="section-editor-heading" className="space-y-3">
        <h2 id="section-editor-heading" className="rf-display text-2xl">
          Temporary section editor
        </h2>
        <SectionEditor
          value={draft.sectionContent}
          onChange={(value) => update('sectionContent', value)}
        />
      </section>

      <p className="text-xs text-[var(--rf-muted)]">
        Similarity checking highlights textual overlap for review. It does not guarantee zero
        plagiarism.
      </p>

      <AuthGateDialog open={gateOpen} actionLabel={gateAction} onClose={() => setGateOpen(false)} />
      <GuestConvertDialog
        open={convertOpen}
        onClose={() => setConvertOpen(false)}
        onConverted={(title) => {
          setStatus(`Saved “${title}” to your private projects.`);
          router.push('/dashboard');
        }}
      />
    </div>
  );
}
