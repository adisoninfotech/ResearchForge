'use client';

import { Button } from '@researchforge/ui';
import { useEffect, useId, useRef, useState } from 'react';
import { api } from '@/lib/api-client';
import {
  clearGuestDraft,
  clearGuestSavePending,
  guestDraftToTransferPayload,
  loadGuestDraft,
} from '@/lib/guest-storage';

interface GuestConvertDialogProps {
  open: boolean;
  onClose: () => void;
  onConverted: (projectTitle: string) => void;
}

export function GuestConvertDialog({ open, onClose, onConverted }: GuestConvertDialogProps) {
  const titleId = useId();
  const confirmRef = useRef<HTMLButtonElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    confirmRef.current?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="w-full max-w-md rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-6"
      >
        <h2 id={titleId} className="rf-display text-2xl">
          Save your temporary draft as a new project?
        </h2>
        <p className="mt-2 text-sm text-[var(--rf-muted)]">
          Your browser-local draft will be transferred once into a private project. Temporary
          storage is cleared only after the server confirms success.
        </p>
        {error ? (
          <p className="mt-3 text-sm text-[var(--rf-danger)]" role="alert">
            {error}
          </p>
        ) : null}
        <div className="mt-6 flex flex-wrap gap-3">
          <Button
            ref={confirmRef}
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                const draft = loadGuestDraft();
                const result = await api.convertGuestDraft(guestDraftToTransferPayload(draft));
                clearGuestDraft();
                clearGuestSavePending();
                onConverted(result.project.title);
                onClose();
              } catch (err) {
                setError(err instanceof Error ? err.message : 'Transfer failed');
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? 'Saving…' : 'Save as project'}
          </Button>
          <Button
            variant="ghost"
            disabled={busy}
            onClick={() => {
              clearGuestSavePending();
              onClose();
            }}
          >
            Not now
          </Button>
        </div>
      </div>
    </div>
  );
}
