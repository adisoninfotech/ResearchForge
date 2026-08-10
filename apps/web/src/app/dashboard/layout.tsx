import Link from 'next/link';
import type { ReactNode } from 'react';

const nav = [
  { href: '/dashboard', label: 'Projects' },
  { href: '/dashboard?status=trash', label: 'Trash' },
  { href: '/workspace', label: 'Guest draft' },
  { href: '/account', label: 'Account' },
  { href: '/privacy', label: 'Privacy' },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl gap-8 px-4 py-8 md:grid-cols-[220px_1fr]">
      <aside className="space-y-4">
        <p className="rf-display text-2xl">Dashboard</p>
        <nav className="flex flex-col gap-1" aria-label="Dashboard">
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-2 text-sm text-[var(--rf-muted)] hover:bg-[var(--rf-surface-2)] hover:text-[var(--rf-fg)]"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <div>{children}</div>
    </div>
  );
}
