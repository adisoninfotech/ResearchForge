import type { Metadata } from 'next';
import Link from 'next/link';
import { Button } from '@researchforge/ui';
import { CitationsSearch } from './citations-search';

export const metadata: Metadata = {
  title: 'Citations',
};

const guidance = [
  'Paste one claim at a time — narrow questions return sharper matches.',
  'Look for the papers with the clearest fit, not the highest count.',
  'Open a promising paper and follow its references — often better than searching again.',
];

export default function CitationsPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-16">
      <header className="max-w-2xl">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--rf-accent)]">
          Citations
        </p>
        <h1 className="rf-display mt-2 text-4xl md:text-5xl">Find papers you can actually cite</h1>
        <p className="mt-4 text-[var(--rf-muted)]">
          Search by topic to discover relevant work, or paste a claim from your draft to find papers
          that could support it — then inspect each one before you cite it.
        </p>
      </header>

      <section className="mt-10 rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface-2)] p-5">
        <h2 className="text-sm font-semibold">Getting good results</h2>
        <ul className="mt-3 space-y-2">
          {guidance.map((item) => (
            <li key={item} className="flex gap-2 text-sm text-[var(--rf-muted)]">
              <span aria-hidden="true" className="text-[var(--rf-accent)]">
                →
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>

      <div className="mt-8">
        <CitationsSearch />
      </div>

      <section className="mt-12 flex flex-wrap items-center justify-between gap-4 rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface-2)] p-6">
        <div>
          <h2 className="text-lg font-semibold">Sign in to save your work</h2>
          <p className="mt-1 text-sm text-[var(--rf-muted)]">
            Guests can search freely. An account keeps projects, references and files.
          </p>
        </div>
        <div className="flex gap-3">
          <Link href="/workspace">
            <Button variant="secondary">Open workspace</Button>
          </Link>
          <Link href="/register">
            <Button>Create account</Button>
          </Link>
        </div>
      </section>

      <p className="mt-8 text-xs text-[var(--rf-muted)]">
        Results come from Crossref, which indexes publisher-deposited metadata. Coverage and
        reference lists vary by publisher, and matching is based on wording rather than meaning — a
        relevant paper phrased differently may not appear.
      </p>
    </div>
  );
}
