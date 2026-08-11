'use client';

import { useState } from 'react';
import { Button, Input, Textarea } from '@researchforge/ui';

type Work = {
  title: string | null;
  authors: string[];
  year: number | null;
  venue: string | null;
  doi: string | null;
  url: string | null;
  cited_by_count: number;
};

type Reference = {
  title: string | null;
  authors: string[];
  year: number | null;
  doi: string | null;
  url: string | null;
  unstructured: string | null;
  linkable: boolean;
};

const API_PREFIX = process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1';

function authorLine(authors: string[]): string {
  if (authors.length === 0) return 'Unknown authors';
  if (authors.length <= 3) return authors.join(', ');
  return `${authors.slice(0, 3).join(', ')} +${authors.length - 3} more`;
}

export function CitationsSearch() {
  const [topic, setTopic] = useState('');
  const [claim, setClaim] = useState('');
  const [results, setResults] = useState<Work[] | null>(null);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Bibliography of whichever result the user expanded.
  const [openDoi, setOpenDoi] = useState<string | null>(null);
  const [refs, setRefs] = useState<Reference[] | null>(null);
  const [refTotal, setRefTotal] = useState(0);
  const [refsLoading, setRefsLoading] = useState(false);

  async function search(q: string) {
    const trimmed = q.trim();
    if (trimmed.length < 3) {
      setError('Enter at least a few words to search for.');
      return;
    }
    setLoading(true);
    setError(null);
    setResults(null);
    setOpenDoi(null);
    setRefs(null);
    setQuery(trimmed);
    try {
      const response = await fetch(`${API_PREFIX}/discovery/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: trimmed, limit: 10 }),
      });
      if (!response.ok) {
        throw new Error(
          response.status === 503
            ? 'Paper search is temporarily unavailable. Try again shortly.'
            : `Search failed (${response.status}).`,
        );
      }
      const data = (await response.json()) as { results: Work[] };
      setResults(data.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed.');
    } finally {
      setLoading(false);
    }
  }

  async function loadReferences(doi: string) {
    if (openDoi === doi) {
      setOpenDoi(null);
      return;
    }
    setOpenDoi(doi);
    setRefs(null);
    setRefsLoading(true);
    try {
      const response = await fetch(
        `${API_PREFIX}/discovery/references?doi=${encodeURIComponent(doi)}&limit=25`,
      );
      if (!response.ok) throw new Error('Could not load the reference list.');
      const data = (await response.json()) as { total: number; references: Reference[] };
      setRefs(data.references);
      setRefTotal(data.total);
    } catch {
      setRefs([]);
      setRefTotal(0);
    } finally {
      setRefsLoading(false);
    }
  }

  return (
    <div>
      <div className="grid gap-6 md:grid-cols-2">
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
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void search(topic);
              }}
              placeholder="e.g. explainable AI and clinician trust"
            />
          </div>
          <div className="mt-4">
            <Button className="w-full" onClick={() => void search(topic)} disabled={loading}>
              {loading ? 'Searching…' : 'Find papers'}
            </Button>
          </div>
        </section>

        <section className="flex flex-col rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-6">
          <h2 className="text-lg font-semibold">Search by claim</h2>
          <p className="mt-1 text-sm font-medium text-[var(--rf-accent)]">
            Match a sentence to possible citations
          </p>
          <p className="mt-3 text-sm leading-relaxed text-[var(--rf-muted)]">
            Paste a claim from your draft and inspect the papers before you cite them.
          </p>
          <div className="mt-5">
            <Textarea
              label="Claim from your draft"
              name="claim"
              value={claim}
              onChange={(e) => setClaim(e.target.value)}
              placeholder="Paste a single sentence making a factual claim…"
            />
          </div>
          <div className="mt-4">
            <Button className="w-full" onClick={() => void search(claim)} disabled={loading}>
              {loading ? 'Searching…' : 'Find citation matches'}
            </Button>
          </div>
        </section>
      </div>

      <section className="mt-10" aria-live="polite">
        {error ? (
          <div
            role="alert"
            className="rounded-lg border border-[var(--rf-danger)] bg-[var(--rf-surface)] p-4 text-sm text-[var(--rf-danger)]"
          >
            {error}
          </div>
        ) : null}

        {loading ? <p className="text-sm text-[var(--rf-muted)]">Searching Crossref…</p> : null}

        {results && results.length === 0 ? (
          <div className="rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-6">
            <h2 className="text-lg font-semibold">No well-cited matches</h2>
            <p className="mt-2 text-sm text-[var(--rf-muted)]">
              Nothing came back for “{query}” with at least one citation. Try wording the claim the
              way the literature would phrase it, or broaden the topic.
            </p>
          </div>
        ) : null}

        {results && results.length > 0 ? (
          <>
            <h2 className="rf-display text-2xl">
              {results.length} paper{results.length === 1 ? '' : 's'} for “{query}”
            </h2>
            <p className="mt-1 text-sm text-[var(--rf-muted)]">
              Ranked by citation count. Always read a paper before citing it.
            </p>
            <ul className="mt-5 space-y-3">
              {results.map((work, i) => (
                <li
                  key={work.doi ?? `${work.title}-${i}`}
                  className="rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-5"
                >
                  <h3 className="font-semibold leading-snug">
                    {work.url ? (
                      <a
                        href={work.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-[var(--rf-accent)] hover:underline"
                      >
                        {work.title}
                      </a>
                    ) : (
                      work.title
                    )}
                  </h3>
                  <p className="mt-1 text-sm text-[var(--rf-muted)]">
                    {authorLine(work.authors)}
                    {work.year ? ` · ${work.year}` : ''}
                    {work.venue ? ` · ${work.venue}` : ''}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                    <span className="rounded-full bg-[var(--rf-surface-2)] px-3 py-1 text-xs">
                      {work.cited_by_count.toLocaleString()} citations
                    </span>
                    {work.doi ? (
                      <button
                        type="button"
                        onClick={() => void loadReferences(work.doi as string)}
                        className="text-[var(--rf-accent)] underline-offset-2 hover:underline"
                      >
                        {openDoi === work.doi ? 'Hide its references' : 'Show its references'}
                      </button>
                    ) : null}
                  </div>

                  {openDoi === work.doi ? (
                    <div className="mt-4 border-t border-[var(--rf-border)] pt-4">
                      {refsLoading ? (
                        <p className="text-sm text-[var(--rf-muted)]">Loading references…</p>
                      ) : refs && refs.length > 0 ? (
                        <>
                          <p className="text-sm text-[var(--rf-muted)]">
                            Showing {refs.length} of {refTotal} references. Entries without a link
                            are stored by Crossref as plain text only.
                          </p>
                          <ul className="mt-3 space-y-2">
                            {refs.map((ref, idx) => (
                              <li key={idx} className="text-sm">
                                {ref.linkable && ref.url ? (
                                  <a
                                    href={ref.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-[var(--rf-accent)] underline-offset-2 hover:underline"
                                  >
                                    {ref.title || ref.doi}
                                  </a>
                                ) : (
                                  <span className="text-[var(--rf-muted)]">
                                    {ref.title || ref.unstructured || 'Untitled reference'}
                                  </span>
                                )}
                                {ref.year ? (
                                  <span className="text-[var(--rf-muted)]"> · {ref.year}</span>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        </>
                      ) : (
                        <p className="text-sm text-[var(--rf-muted)]">
                          Crossref holds no reference list for this paper. Publishers deposit these
                          voluntarily, so coverage is uneven.
                        </p>
                      )}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </section>
    </div>
  );
}
