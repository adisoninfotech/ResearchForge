'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Button } from '@researchforge/ui';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import { useAuth } from '@/components/auth-provider';

function VerifyEmailForm() {
  const params = useSearchParams();
  const token = params.get('token') || '';
  const { refresh } = useAuth();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <div className="mx-auto mt-16 w-full max-w-md space-y-4 px-4">
      <h1 className="rf-display text-4xl">Verify email</h1>
      <p className="text-sm text-[var(--rf-muted)]">
        Confirm your email address to finish setting up your ResearchForge account.
      </p>
      {message ? <p className="text-sm text-[var(--rf-accent)]">{message}</p> : null}
      {error ? (
        <p className="text-sm text-[var(--rf-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      <Button
        disabled={!token || busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            const result = await api.verifyEmail(token);
            setMessage(result.message);
            await refresh();
          } catch (err) {
            setError(err instanceof Error ? err.message : 'Verification failed');
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? 'Verifying…' : 'Verify email'}
      </Button>
      <Link href="/dashboard" className="block text-sm underline">
        Go to dashboard
      </Link>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<p className="p-8 text-sm text-[var(--rf-muted)]">Loading…</p>}>
      <VerifyEmailForm />
    </Suspense>
  );
}
