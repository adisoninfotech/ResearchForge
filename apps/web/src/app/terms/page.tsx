import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Terms',
};

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="rf-display text-4xl">Terms</h1>
      <div className="mt-6 space-y-4 text-[var(--rf-muted)]">
        <p>
          ResearchForge is provided for scholarly research support. You remain responsible for the
          accuracy, originality, and ethical use of manuscripts you produce.
        </p>
        <p>
          Guests may generate limited previews. Saving projects, permanent uploads, complete
          manuscript downloads, full similarity checks, and full section generation require an
          authenticated account.
        </p>
        <p>
          Do not upload content you are not authorized to process. Accounts that abuse the service
          may be suspended.
        </p>
      </div>
    </div>
  );
}
