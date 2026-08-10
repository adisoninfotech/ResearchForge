import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';

const apiDir = path.resolve(__dirname, '../api');
const apiPython =
  process.platform === 'win32'
    ? path.join(apiDir, '.venv', 'Scripts', 'python.exe')
    : path.join(apiDir, '.venv', 'bin', 'python');

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:3000',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: `${apiPython} scripts/prepare_playwright_db.py && ${apiPython} -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: apiDir,
      url: 'http://127.0.0.1:8000/health/live',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        ...process.env,
        APP_ENV: 'test',
        AI_PROVIDER: 'fake',
        EMAIL_PROVIDER: 'fake',
        RATE_LIMIT_ENABLED: 'false',
        SECRET_KEY: 'playwright-secret-key-not-for-production',
        CSRF_SECRET: 'playwright-csrf-secret-not-for-production',
        DATABASE_URL: 'sqlite+aiosqlite:///./playwright-auth.db',
        CORS_ORIGINS: 'http://127.0.0.1:3000,http://localhost:3000',
        PUBLIC_APP_URL: 'http://127.0.0.1:3000',
        GOOGLE_OAUTH_ENABLED: 'false',
      },
    },
    {
      command: 'npm run dev -- --hostname 127.0.0.1 --port 3000',
      url: 'http://127.0.0.1:3000',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        ...process.env,
        NEXT_PUBLIC_APP_URL: 'http://127.0.0.1:3000',
        NEXT_PUBLIC_API_URL: 'http://127.0.0.1:3000',
        NEXT_PUBLIC_API_PREFIX: '/api/v1',
        API_PROXY_TARGET: 'http://127.0.0.1:8000',
      },
    },
  ],
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
