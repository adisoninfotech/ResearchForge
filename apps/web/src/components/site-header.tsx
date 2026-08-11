'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState } from 'react';
import { Button, cn } from '@researchforge/ui';
import { useAuth } from './auth-provider';

const links = [
  { href: '/workspace', label: 'Workspace' },
  { href: '/citations', label: 'Citations' },
  { href: '/pricing', label: 'Pricing' },
  { href: '/privacy', label: 'Privacy' },
  // Terms is deliberately not here — it is a legal page rather than a
  // day-to-day destination, and lives in the site footer instead.
  { href: '/contact', label: 'Contact us' },
];

export function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--rf-border)] bg-[var(--rf-surface)] backdrop-blur">
      {/* Full-bleed rather than max-w-6xl so the logo sits in the actual
          top-left corner instead of being inset by the centred container. */}
      {/* No justify-between: that left the nav floating in the middle. The nav
          carries ml-auto instead, so it and the account actions group together
          on the right with the logo alone on the left. */}
      <div className="flex h-16 w-full items-center gap-4 px-4 sm:px-6">
        <Link
          href="/"
          className="flex shrink-0 flex-col items-start gap-1"
          aria-label="ResearchForge home"
        >
          {/* Cropped to the mark + wordmark. The tagline below is real text,
              not part of the image: baked in it would be ~4px tall here, and
              its near-black ink would vanish against the dark theme. The 8px
              size with 0.18em tracking makes it span roughly the same width as
              the 32px-tall wordmark, so the two line up. */}
          <Image
            src="/logo-wordmark.png"
            alt="ResearchForge"
            width={1660}
            height={290}
            priority
            className="h-8 w-auto"
          />
          <span className="hidden text-[8px] font-medium uppercase leading-none tracking-[0.18em] text-[var(--rf-muted)] sm:block">
            Discover · Analyze · Innovate
          </span>
        </Link>
        <nav className="ml-auto hidden items-center gap-1 md:flex" aria-label="Primary">
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
        {/* No theme toggle: ThemeProvider runs with defaultTheme="system" and
            enableSystem, so the theme follows each visitor's OS preference. */}
        <div className="hidden items-center gap-2 md:flex">
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
          className="ml-auto rounded-md border border-[var(--rf-border)] px-3 py-2 text-sm md:hidden"
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
          </nav>
        </div>
      ) : null}
    </header>
  );
}
