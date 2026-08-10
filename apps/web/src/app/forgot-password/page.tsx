'use client';

import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button, Input } from '@researchforge/ui';
import { useState } from 'react';
import { api } from '@/lib/api-client';

const schema = z.object({
  email: z.string().email(),
});

type FormValues = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
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
          const result = await api.forgotPassword(values.email);
          setMessage(result.message);
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Request failed');
        }
      })}
    >
      <h1 className="rf-display text-4xl">Forgot password</h1>
      <p className="text-sm text-[var(--rf-muted)]">
        We will send reset instructions if an account exists for that email.
      </p>
      <Input
        label="Email"
        type="email"
        autoComplete="email"
        error={errors.email?.message}
        {...register('email')}
      />
      {message ? <p className="text-sm text-[var(--rf-accent)]">{message}</p> : null}
      {error ? (
        <p className="text-sm text-[var(--rf-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? 'Sending…' : 'Send reset link'}
      </Button>
      <Link href="/login" className="block text-sm underline">
        Back to sign in
      </Link>
    </form>
  );
}
