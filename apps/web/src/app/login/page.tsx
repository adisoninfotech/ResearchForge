'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button, Input } from '@researchforge/ui';
import { Suspense, useState } from 'react';
import { api } from '@/lib/api-client';
import { useAuth } from '@/components/auth-provider';
import { markGuestSavePending } from '@/lib/guest-storage';

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1, 'Password is required'),
  remember_me: z.boolean().default(false),
});

type FormValues = z.infer<typeof schema>;

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get('next') || '/dashboard';
  const { setUser } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { remember_me: false },
  });

  return (
    <form
      className="mx-auto mt-16 w-full max-w-md space-y-4 px-4"
      onSubmit={handleSubmit(async (values) => {
        setError(null);
        try {
          const result = await api.login({
            email: values.email,
            password: values.password,
            remember_me: values.remember_me,
          });
          setUser(result.user);
          if (next.includes('workspace') || searchParams.get('save') === '1') {
            markGuestSavePending();
          }
          router.push(next);
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Login failed');
        }
      })}
    >
      <h1 className="rf-display text-4xl">Sign in</h1>
      <p className="text-sm text-[var(--rf-muted)]">
        After login you can transfer a temporary guest draft into a saved project.
      </p>
      <Input
        label="Email"
        type="email"
        autoComplete="email"
        error={errors.email?.message}
        {...register('email')}
      />
      <Input
        label="Password"
        type="password"
        autoComplete="current-password"
        error={errors.password?.message}
        {...register('password')}
      />
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" {...register('remember_me')} />
        Remember me on this device
      </label>
      {error ? (
        <p className="text-sm text-[var(--rf-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? 'Signing in…' : 'Sign in'}
      </Button>
      <div className="flex justify-between text-sm">
        <Link href="/forgot-password" className="underline">
          Forgot password
        </Link>
        <Link href={`/register?next=${encodeURIComponent(next)}`} className="underline">
          Create account
        </Link>
      </div>
    </form>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="p-8 text-sm text-[var(--rf-muted)]">Loading…</p>}>
      <LoginForm />
    </Suspense>
  );
}
