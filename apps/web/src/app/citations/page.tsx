import type { Metadata } from 'next';
import Link from 'next/link';
import { Button, Input, Textarea } from '@researchforge/ui';

export const metadata: Metadata = {
  title: 'Citations',
};

// ---------------------------------------------------------------------------
// LAYOUT PREVIEW ONLY — NOT WIRED TO ANYTHING.
//
// This page mirrors the examforge.courses/search layout so the design can be
// judged. The controls are deliberately inert: the API has no external paper
// search. There is no OpenAlex, Crossref or Semantic Scholar integration in
// apps/api — the only search endpoint is POST /api/v1/search, which runs a
// hybrid search over evidence already uploaded to a project
// (apps/api/app/api/v1/files.py:172), not paper discovery.
//
// Before this can ship, either:
//   a) build an OpenAlex service + endpoint in the API (OpenAlex is free and
//      needs no key), or
//   b) repoint this page at the existing /search endpoint and reframe it as
//      "search your own sources".
//
// Until then the banner below must stay, so nobody mistakes it for working.
// ---------------------------------------------------------------------------

const guidance = [
  'Paste one claim at a time — narrow questions return sharper matches.',
  'Look for the papers with the clearest fit, not the highest count.',
  'Bring the best sources back into your project before you cite them.',
];

export default function CitationsPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-16">
      <div
        role="note"
        className="mb-10 rounded-lg border border-dashed border-[var(--rf-danger)] bg-[var(--rf-surface)] p-4"
      >
        <p className="text-sm font-semibold text-[var(--rf-danger)]">
          Design preview — not connected
        </p>
        <p className="mt-1 text-sm text-[var(--rf-muted)]">
          The controls on this page do nothing yet. Paper discovery needs a backend integration
          (OpenAlex or Crossref) that does not exist in the API yet.
        </p>
      </div>

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

      <div className="mt-8 grid gap-6 md:grid-cols-2">
        <section className="flex flex-col rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-6">
          <h2 className="text-lg font-semibold">Search by topic</h2>
          <p className="mt-1 text-sm font-medium text-[var(--rf-accent)]">Find supporting papers</p>
          <p className="mt-3 text-sm leading-relaxed text-[var(--rf-muted)]">
            Look for papers related to a topic, a method, or a research question.
          </p>
          <div className="mt-5">
            <Input
              label="Topic or research question"
              name="topic"
              placeholder="e.g. transformer models for protein folding"
              disabled
            />
          </div>
          <div className="mt-4">
            <Button className="w-full" disabled>
              Find papers
            </Button>
          </div>
        </section>

        <section className="flex flex-col rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-6">
          <h2 className="text-lg font-semibold">Search by claim</h2>
          <p className="mt-1 text-sm font-medium text-[var(--rf-accent)]">
            Match a sentence to possible citations
          </p>
          <p className="mt-3 text-sm leading-relaxed text-[var(--rf-muted)]">
            Paste a claim from your draft and get a tighter search query plus papers you can inspect
            before citing.
          </p>
          <div className="mt-5">
            <Textarea
              label="Claim from your draft"
              name="claim"
              placeholder="Paste a single sentence making a factual claim…"
              disabled
            />
          </div>
          <div className="mt-4">
            <Button className="w-full" disabled>
              Find citation matches
            </Button>
          </div>
        </section>
      </div>

      <section className="mt-10 rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-6">
        <h2 className="text-lg font-semibold">Results</h2>
        <p className="mt-2 text-sm text-[var(--rf-muted)]">
          Matching papers will appear here — title, authors, year and DOI, each with a link to the
          source and an option to add it to your project references.
        </p>
        <div className="mt-5 space-y-3" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="rounded-md border border-dashed border-[var(--rf-border)] p-4 opacity-50"
            >
              <div className="h-4 w-2/3 rounded bg-[var(--rf-surface-3)]" />
              <div className="mt-2 h-3 w-1/3 rounded bg-[var(--rf-surface-3)]" />
              <div className="mt-3 h-3 w-full rounded bg-[var(--rf-surface-3)]" />
            </div>
          ))}
        </div>
      </section>

      <section className="mt-10 flex flex-wrap items-center justify-between gap-4 rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface-2)] p-6">
        <div>
          <h2 className="text-lg font-semibold">Sign in to save your work</h2>
          <p className="mt-1 text-sm text-[var(--rf-muted)]">
            Guests can explore in the browser. An account keeps projects, references and files.
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
    </div>
  );
}
