'use client';

import Link from 'next/link';
import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button, Input } from '@researchforge/ui';
import { api } from '@/lib/api-client';

const schema = z.object({
  new_password: z.string().min(8, 'Use at least 8 characters'),
});

type FormValues = z.infer<typeof schema>;

function ResetPasswordForm() {
  const params = useSearchParams();
  const token = params.get('token') || '';
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  return (
    <form
      className="mx-auto mt-16 w-full max-w-md space-y-4 px-4"
      onSubmit={handleSubmit(async (values) => {
        setError(null);
        setMessage(null);
        try {
          const result = await api.resetPassword(token, values.new_password);
          setMessage(result.message);
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Reset failed');
        }
      })}
    >
      <h1 className="rf-display text-4xl">Reset password</h1>
      <Input
        label="New password"
        type="password"
        autoComplete="new-password"
        error={errors.new_password?.message}
        {...register('new_password')}
      />
      {message ? <p className="text-sm text-[var(--rf-accent)]">{message}</p> : null}
      {error ? (
        <p className="text-sm text-[var(--rf-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      <Button type="submit" disabled={!token || isSubmitting} className="w-full">
        {isSubmitting ? 'Updating…' : 'Update password'}
      </Button>
      <Link href="/login" className="block text-sm underline">
        Back to sign in
      </Link>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<p className="p-8 text-sm text-[var(--rf-muted)]">Loading…</p>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
