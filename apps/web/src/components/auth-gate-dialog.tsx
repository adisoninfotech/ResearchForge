'use client';

import Link from 'next/link';
import { useEffect, useId, useRef } from 'react';
import { Button } from '@researchforge/ui';

interface AuthGateDialogProps {
  open: boolean;
  actionLabel: string;
  onClose: () => void;
}

export function AuthGateDialog({ open, actionLabel, onClose }: AuthGateDialogProps) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const next = actionLabel === 'Save' ? '/dashboard?convert=1' : '/workspace';

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="presentation"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="w-full max-w-md rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-6 shadow-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id={titleId} className="rf-display text-2xl">
          Sign in to continue
        </h2>
        <p className="mt-2 text-sm text-[var(--rf-muted)]">
          {actionLabel} requires an account. Guests can explore and keep a temporary draft in this
          browser, but cannot save projects on the server, permanently upload documents, or download
          complete manuscripts.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href={`/login?next=${encodeURIComponent(next)}&save=${actionLabel === 'Save' ? '1' : '0'}`}
          >
            <Button>Sign in</Button>
          </Link>
          <Link
            href={`/register?next=${encodeURIComponent(next)}&save=${actionLabel === 'Save' ? '1' : '0'}`}
          >
            <Button variant="secondary">Create account</Button>
          </Link>
          <Button ref={closeRef} variant="ghost" onClick={onClose}>
            Keep editing as guest
          </Button>
        </div>
      </div>
    </div>
  );
}
