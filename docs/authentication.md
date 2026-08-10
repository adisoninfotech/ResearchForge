# Authentication & session model

## Overview

ResearchForge uses **server-side sessions** with:

- Short-lived JWT **access** tokens (`rf_access`, HTTP-only)
- Rotating opaque **refresh** tokens (`rf_refresh`, HTTP-only, path-scoped)
- Signed **CSRF** tokens echoed via `X-CSRF-Token` (double-submit)

Passwords are hashed with **Argon2id**. Refresh, email verification, and password-reset secrets are stored only as SHA-256 hashes.

## Cookie flags

| Cookie       | HttpOnly | Secure                  | SameSite                     | Purpose                |
| ------------ | -------- | ----------------------- | ---------------------------- | ---------------------- |
| `rf_access`  | yes      | forced on in production | configurable (`lax` default) | Access JWT             |
| `rf_refresh` | yes      | forced on in production | configurable                 | Rotating refresh token |
| `rf_csrf`    | no       | forced on in production | configurable                 | Double-submit CSRF     |

`COOKIE_SECURE` is honored in non-production; production always sets Secure cookies.

## CSRF

Mutating authenticated routes require:

1. CSRF cookie present
2. Matching `X-CSRF-Token` header
3. Cryptographic signature validation

Login/register establish cookies and return `csrf_token` in the JSON body. The Next.js app proxies `/api/*` to the API (`API_PROXY_TARGET`) so auth cookies are first-party on the web origin and work with `SameSite=Lax`.

## Session lifecycle

- Login / register create an `auth_sessions` row
- Refresh rotates the refresh token hash and keeps the previous hash for **reuse detection**
- Reuse of a previous refresh token revokes **all** sessions for that user
- Logout revokes the current session
- Password reset and account deletion revoke all sessions
- `last_seen_at` updates at most once per `SESSION_LAST_SEEN_MIN_INTERVAL_SECONDS` (default 300)

## Guest conversion

Guest manuscript data stays in browser storage only. After authentication, `POST /api/v1/projects/from-guest` creates a private project. `guest_conversion_key` makes conversion idempotent per user.

## Google OAuth

Interface and status endpoint exist. Google remains **disabled** unless:

```env
GOOGLE_OAUTH_ENABLED=true
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/auth/oauth/google/callback
```

No OAuth client secrets are stored in the database; only provider subject identifiers are linked in `oauth_accounts`.

## Email

Development/test use `EMAIL_PROVIDER=console|fake`. Verification and reset links point at `PUBLIC_APP_URL`.
