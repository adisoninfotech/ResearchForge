import { afterEach, describe, expect, it, vi } from 'vitest';
import { getApiBaseUrl, getPublicEnv } from './env';

describe('env', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('provides defaults for local development', () => {
    vi.stubEnv('NEXT_PUBLIC_APP_URL', undefined);
    vi.stubEnv('NEXT_PUBLIC_API_URL', undefined);
    vi.stubEnv('NEXT_PUBLIC_API_PREFIX', undefined);
    const env = getPublicEnv();
    expect(env.NEXT_PUBLIC_APP_URL).toBe('http://localhost:3000');
    expect(getApiBaseUrl()).toBe('http://localhost:3000/api/v1');
  });
});
