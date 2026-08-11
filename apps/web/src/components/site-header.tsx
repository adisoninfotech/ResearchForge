'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState } from 'react';
import { Button, cn } from '@researchforge/ui';
import { useAuth } from './auth-provider';
import { ThemeToggle } from './theme-toggle';

const links = [
  { href: '/workspace', label: 'Workspace' },
  { href: '/citations', label: 'Citations' },
  { href: '/pricing', label: 'Pricing' },
  { href: '/privacy', label: 'Privacy' },
  { href: '/terms', label: 'Terms' },
];

export function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--rf-border)] bg-[var(--rf-surface)] backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Link
          href="/"
          className="rf-display text-2xl tracking-tight"
          aria-label="ResearchForge home"
        >
          ResearchForge
        </Link>
        <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                'rounded-md px-3 py-2 text-sm text-[var(--rf-muted)] hover:text-[var(--rf-fg)]',
                pathname === link.href && 'bg-[var(--rf-surface-2)] text-[var(--rf-fg)]',
              )}
            >
              {link.label}
            </Link>
          ))}
          {user ? (
            <>
              <Link
                href="/dashboard"
                className={cn(
                  'rounded-md px-3 py-2 text-sm text-[var(--rf-muted)] hover:text-[var(--rf-fg)]',
                  pathname.startsWith('/dashboard') &&
                    'bg-[var(--rf-surface-2)] text-[var(--rf-fg)]',
                )}
              >
                Dashboard
              </Link>
              <Link
                href="/account"
                className={cn(
                  'rounded-md px-3 py-2 text-sm text-[var(--rf-muted)] hover:text-[var(--rf-fg)]',
                  pathname.startsWith('/account') && 'bg-[var(--rf-surface-2)] text-[var(--rf-fg)]',
                )}
              >
                Account
              </Link>
            </>
          ) : null}
        </nav>
        <div className="hidden items-center gap-2 md:flex">
          <ThemeToggle />
          {loading ? null : user ? (
            <>
              <span className="max-w-[10rem] truncate text-sm text-[var(--rf-muted)]">
                {user.display_name || user.email}
              </span>
              <Button
                size="sm"
                variant="ghost"
                onClick={async () => {
                  await logout();
                  router.push('/');
                }}
              >
                Log out
              </Button>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="inline-flex h-9 items-center rounded-md px-3 text-sm hover:bg-[var(--rf-surface-2)]"
              >
                Sign in
              </Link>
              <Link href="/register">
                <Button size="sm">Create account</Button>
              </Link>
            </>
          )}
        </div>
        <button
          type="button"
          className="rounded-md border border-[var(--rf-border)] px-3 py-2 text-sm md:hidden"
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen((v) => !v)}
        >
          Menu
        </button>
      </div>
      {open ? (
        <div id="mobile-nav" className="border-t border-[var(--rf-border)] px-4 py-3 md:hidden">
          <nav className="flex flex-col gap-1" aria-label="Mobile">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="rounded-md px-2 py-2 text-sm"
                onClick={() => setOpen(false)}
              >
                {link.label}
              </Link>
            ))}
            {user ? (
              <>
                <Link
                  href="/dashboard"
                  className="rounded-md px-2 py-2 text-sm"
                  onClick={() => setOpen(false)}
                >
                  Dashboard
                </Link>
                <Link
                  href="/account"
                  className="rounded-md px-2 py-2 text-sm"
                  onClick={() => setOpen(false)}
                >
                  Account
                </Link>
                <button
                  type="button"
                  className="rounded-md px-2 py-2 text-left text-sm"
                  onClick={async () => {
                    setOpen(false);
                    await logout();
                    router.push('/');
                  }}
                >
                  Log out
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  className="rounded-md px-2 py-2 text-sm"
                  onClick={() => setOpen(false)}
                >
                  Sign in
                </Link>
                <Link
                  href="/register"
                  className="rounded-md px-2 py-2 text-sm"
                  onClick={() => setOpen(false)}
                >
                  Create account
                </Link>
              </>
            )}
            <ThemeToggle />
          </nav>
        </div>
      ) : null}
    </header>
  );
}
