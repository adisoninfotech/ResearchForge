import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Privacy',
};

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 prose-none">
      <h1 className="rf-display text-4xl">Privacy</h1>
      <div className="mt-6 space-y-4 text-[var(--rf-muted)]">
        <p>
          User content on ResearchForge is private by default. Guest drafts remain in your browser
          and are not stored as projects on our servers.
        </p>
        <p>
          We do not use your content for model training unless you explicitly opt in from your
          account settings.
        </p>
        <p>
          Synthetic datasets and simulated results are labeled so they are not mistaken for observed
          experimental data.
        </p>
        <p>
          Similarity checking helps you review textual overlap. It does not guarantee zero
          plagiarism.
        </p>
      </div>
    </div>
  );
}
