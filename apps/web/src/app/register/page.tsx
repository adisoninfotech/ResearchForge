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
  display_name: z.string().max(255).optional(),
  email: z.string().email(),
  password: z.string().min(8, 'Use at least 8 characters'),
  training_opt_in: z.boolean().default(false),
});

type FormValues = z.infer<typeof schema>;

function RegisterForm() {
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
    defaultValues: { training_opt_in: false },
  });

  return (
    <form
      className="mx-auto mt-16 w-full max-w-md space-y-4 px-4"
      onSubmit={handleSubmit(async (values) => {
        setError(null);
        try {
          const result = await api.register({
            email: values.email,
            password: values.password,
            display_name: values.display_name,
            training_opt_in: values.training_opt_in,
          });
          setUser(result.user);
          if (next.includes('workspace') || searchParams.get('save') === '1') {
            markGuestSavePending();
          }
          router.push(next);
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Registration failed');
        }
      })}
    >
      <h1 className="rf-display text-4xl">Create account</h1>
      <p className="text-sm text-[var(--rf-muted)]">
        Content is private by default and is not used for model training unless you opt in.
      </p>
      <Input
        label="Display name"
        autoComplete="name"
        error={errors.display_name?.message}
        {...register('display_name')}
      />
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
        autoComplete="new-password"
        error={errors.password?.message}
        {...register('password')}
      />
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-1" {...register('training_opt_in')} />
        <span>
          I opt in to allow ResearchForge to use my content for model training. Leave unchecked to
          keep content out of training.
        </span>
      </label>
      {error ? (
        <p className="text-sm text-[var(--rf-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? 'Creating…' : 'Create account'}
      </Button>
      <p className="text-sm">
        Already have an account?{' '}
        <Link href={`/login?next=${encodeURIComponent(next)}`} className="underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<p className="p-8 text-sm text-[var(--rf-muted)]">Loading…</p>}>
      <RegisterForm />
    </Suspense>
  );
}
