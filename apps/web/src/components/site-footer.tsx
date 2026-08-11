import Link from 'next/link';

// Privacy and Terms live here rather than in the header tab bar. They are
// legal pages that must stay reachable from every page, but nobody navigates
// to them as a primary destination.
const legal = [
  { href: '/privacy', label: 'Privacy' },
  { href: '/terms', label: 'Terms' },
  { href: '/contact', label: 'Contact us' },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-[var(--rf-border)]">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-[var(--rf-muted)]">
        <p>An Adison Infotech product</p>
        <nav className="flex flex-wrap items-center gap-4" aria-label="Footer">
          {legal.map((item) => (
            <Link key={item.href} href={item.href} className="hover:text-[var(--rf-accent)]">
              {item.label}
            </Link>
          ))}
          <a
            href="mailto:info@adisoninfotech.co.uk?subject=ResearchForge%20enquiry"
            className="hover:text-[var(--rf-accent)]"
          >
            info@adisoninfotech.co.uk
          </a>
        </nav>
      </div>
    </footer>
  );
}
