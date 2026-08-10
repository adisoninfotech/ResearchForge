'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import type { SessionPublic } from '@researchforge/shared-types';
import { Button, Notice } from '@researchforge/ui';
import { useAuth } from '@/components/auth-provider';
import { api } from '@/lib/api-client';

export default function SessionsPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [sessions, setSessions] = useState<SessionPublic[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const rows = await api.listSessions();
    setSessions(rows);
  }

  useEffect(() => {
    if (!loading && !user) router.replace('/login?next=/account/sessions');
  }, [loading, user, router]);

  useEffect(() => {
    if (user) void load().catch((err: Error) => setError(err.message));
  }, [user]);

  if (loading || !user) {
    return <p className="p-8 text-sm text-[var(--rf-muted)]">Loading sessions…</p>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-12">
      <h1 className="rf-display text-4xl">Active sessions</h1>
      <Notice>
        Revoking a session signs that device out. Password resets and account deletion revoke all
        sessions automatically.
      </Notice>
      {message ? <p className="text-sm text-[var(--rf-accent)]">{message}</p> : null}
      {error ? (
        <p className="text-sm text-[var(--rf-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      <Button
        variant="secondary"
        onClick={async () => {
          setError(null);
          try {
            const result = await api.revokeOtherSessions();
            setMessage(result.message);
            await load();
          } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to revoke sessions');
          }
        }}
      >
        Revoke all other sessions
      </Button>
      <ul className="space-y-3">
        {sessions.map((session) => (
          <li
            key={session.id}
            className="rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] p-4"
          >
            <p className="font-medium">
              {session.device_name || 'Unknown device'}
              {session.is_current ? ' · current' : ''}
              {session.remember_me ? ' · remember me' : ''}
            </p>
            <p className="text-sm text-[var(--rf-muted)]">
              {session.user_agent || 'No user agent'}
            </p>
            <p className="text-xs text-[var(--rf-muted)]">
              Last seen {new Date(session.last_seen_at).toLocaleString()}
            </p>
            {!session.is_current ? (
              <Button
                size="sm"
                variant="ghost"
                className="mt-2"
                onClick={async () => {
                  setError(null);
                  try {
                    await api.revokeSession(session.id);
                    setMessage('Session revoked');
                    await load();
                  } catch (err) {
                    setError(err instanceof Error ? err.message : 'Failed to revoke session');
                  }
                }}
              >
                Revoke session
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
