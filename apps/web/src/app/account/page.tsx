'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button, Input, Notice } from '@researchforge/ui';
import { useAuth } from '@/components/auth-provider';
import { api } from '@/lib/api-client';

function NotificationPreferencesSection() {
  const [prefs, setPrefs] = useState<Record<string, boolean>>({});
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [note, setNote] = useState('');
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    void api.getNotificationPreferences().then((res) => {
      setPrefs(res.preferences);
      setLabels(res.labels);
      setNote(res.note);
    });
  }, []);

  return (
    <section className="space-y-3" aria-labelledby="notif-prefs-heading">
      <h2 id="notif-prefs-heading" className="rf-display text-2xl">
        Notification preferences
      </h2>
      <p className="text-sm text-[var(--rf-muted)]">{note}</p>
      <ul className="space-y-2">
        {Object.keys(prefs).map((key) => (
          <li key={key}>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1 focus-visible:outline focus-visible:outline-2"
                checked={Boolean(prefs[key])}
                onChange={(e) => setPrefs((prev) => ({ ...prev, [key]: e.target.checked }))}
              />
              <span>{labels[key] || key}</span>
            </label>
          </li>
        ))}
      </ul>
      <Button
        type="button"
        onClick={async () => {
          setStatus(null);
          await api.updateNotificationPreferences(prefs);
          setStatus('Notification preferences saved');
        }}
      >
        Save notification preferences
      </Button>
      {status ? <p className="text-sm text-[var(--rf-accent)]">{status}</p> : null}
    </section>
  );
}

const schema = z.object({
  display_name: z.string().max(255).optional(),
  training_opt_in: z.boolean(),
});

type FormValues = z.infer<typeof schema>;

export default function AccountSettingsPage() {
  const router = useRouter();
  const { user, loading, setUser, logout } = useAuth();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletePassword, setDeletePassword] = useState('');
  const {
    register,
    handleSubmit,
    reset,
    formState: { isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { training_opt_in: false },
  });

  useEffect(() => {
    if (!loading && !user) router.replace('/login?next=/account');
  }, [loading, user, router]);

  useEffect(() => {
    if (user) {
      reset({
        display_name: user.display_name || '',
        training_opt_in: user.training_opt_in,
      });
    }
  }, [user, reset]);

  if (loading || !user) {
    return <p className="p-8 text-sm text-[var(--rf-muted)]">Loading account…</p>;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-10 px-4 py-12">
      <div>
        <h1 className="rf-display text-4xl">Account settings</h1>
        <p className="mt-2 text-sm text-[var(--rf-muted)]">{user.email}</p>
        <p className="text-sm text-[var(--rf-muted)]">
          Email {user.email_verified ? 'verified' : 'not verified yet'}.
        </p>
      </div>

      <form
        className="space-y-4"
        onSubmit={handleSubmit(async (values) => {
          setError(null);
          setMessage(null);
          try {
            const updated = await api.updateAccount({
              display_name: values.display_name,
              training_opt_in: values.training_opt_in,
            });
            setUser(updated);
            setMessage('Account updated');
          } catch (err) {
            setError(err instanceof Error ? err.message : 'Update failed');
          }
        })}
      >
        <Input label="Display name" {...register('display_name')} />
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" {...register('training_opt_in')} />
          <span>
            Allow my content to be used for model training. Off by default; content remains private
            unless you opt in.
          </span>
        </label>
        {message ? <p className="text-sm text-[var(--rf-accent)]">{message}</p> : null}
        {error ? (
          <p className="text-sm text-[var(--rf-danger)]" role="alert">
            {error}
          </p>
        ) : null}
        <Button type="submit" disabled={isSubmitting}>
          Save changes
        </Button>
      </form>

      <NotificationPreferencesSection />

      <div className="space-y-3">
        <h2 className="rf-display text-2xl">Sessions</h2>
        <Link href="/account/sessions" className="text-sm underline">
          Manage active sessions
        </Link>
      </div>

      <div className="space-y-3">
        <h2 className="rf-display text-2xl">Delete account</h2>
        <Notice>
          Deleting your account revokes all sessions and soft-deletes your profile. Type your
          password to confirm.
        </Notice>
        <Input
          label="Password"
          type="password"
          value={deletePassword}
          onChange={(e) => setDeletePassword(e.target.value)}
        />
        <Button
          variant="danger"
          onClick={async () => {
            setError(null);
            try {
              await api.deleteAccount(deletePassword);
              await logout();
              router.push('/');
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Deletion failed');
            }
          }}
        >
          Delete my account
        </Button>
      </div>
    </div>
  );
}
