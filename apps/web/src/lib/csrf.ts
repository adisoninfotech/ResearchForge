const CSRF_STORAGE_KEY = 'researchforge.csrf';

export function storeCsrfToken(token: string | null | undefined): void {
  if (typeof window === 'undefined' || !token) return;
  window.sessionStorage.setItem(CSRF_STORAGE_KEY, token);
}

export function clearCsrfToken(): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.removeItem(CSRF_STORAGE_KEY);
}

export function readCsrfToken(): string | null {
  if (typeof window === 'undefined') return null;
  const stored = window.sessionStorage.getItem(CSRF_STORAGE_KEY);
  if (stored) return stored;
  // Same-origin deployments may expose the cookie to document.cookie
  const match = document.cookie.match(/(?:^|; )rf_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}
