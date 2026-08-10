import { z } from 'zod';

const envSchema = z.object({
  NEXT_PUBLIC_APP_URL: z.string().url().default('http://localhost:3000'),
  // Same-origin by default so HTTP-only cookies work with SameSite=Lax via Next rewrites.
  NEXT_PUBLIC_API_URL: z.string().url().default('http://localhost:3000'),
  NEXT_PUBLIC_API_PREFIX: z.string().default('/api/v1'),
});

export type PublicEnv = z.infer<typeof envSchema>;

export function getPublicEnv(): PublicEnv {
  const parsed = envSchema.safeParse({
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_API_PREFIX: process.env.NEXT_PUBLIC_API_PREFIX,
  });

  if (!parsed.success) {
    throw new Error(`Invalid public environment: ${parsed.error.message}`);
  }
  return parsed.data;
}

export function getApiBaseUrl(): string {
  const env = getPublicEnv();
  return `${env.NEXT_PUBLIC_API_URL.replace(/\/$/, '')}${env.NEXT_PUBLIC_API_PREFIX}`;
}
