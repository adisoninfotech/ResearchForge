import Link from 'next/link';
import { Button } from '@researchforge/ui';

type Action = {
  label: string;
  description: string;
  href: string;
};

const startActions: Action[] = [
  {
    label: 'Open workspace',
    description: 'Start drafting straight away — no account needed to explore.',
    href: '/workspace',
  },
  {
    label: 'Draft an outline',
    description: 'Turn a research question into a structured manuscript skeleton.',
    href: '/workspace',
  },
  {
    label: 'Upload your sources',
    description: 'PDFs, Word documents and spreadsheets, parsed into searchable evidence.',
    href: '/workspace',
  },
  {
    label: 'Check similarity',
    description: 'See where your text overlaps with your sources before you submit.',
    href: '/workspace',
  },
];

const capabilities: Action[] = [
  {
    label: 'Ground every claim',
    description:
      'Each generated sentence links back to the passage it came from, so you can verify before you cite.',
    href: '/workspace',
  },
  {
    label: 'Manage references',
    description: 'Import BibTeX and RIS, deduplicate entries, and keep citations consistent.',
    href: '/workspace',
  },
  {
    label: 'Analyse datasets',
    description: 'Upload CSVs, run descriptive and inferential statistics, generate figures.',
    href: '/workspace',
  },
  {
    label: 'Build tables and figures',
    description: 'Publication-ready output generated from your own data, not invented.',
    href: '/workspace',
  },
  {
    label: 'Export to journal formats',
    description: 'Complete manuscripts as DOCX or PDF, with references formatted correctly.',
    href: '/workspace',
  },
  {
    label: 'Keep your work private',
    description: 'Projects stay yours. Training on your content is off unless you opt in.',
    href: '/privacy',
  },
];

const steps = [
  {
    number: '01',
    title: 'Bring your evidence',
    body: 'Upload papers, notes and datasets. ResearchForge extracts the text, splits it into passages, and indexes it.',
  },
  {
    number: '02',
    title: 'Draft against it',
    body: 'Generate outlines and sections that quote your sources directly, with every claim traceable to a passage.',
  },
  {
    number: '03',
    title: 'Check and export',
    body: 'Run a similarity report, review the flagged overlaps, then export a complete manuscript.',
  },
];

function ActionCard({ action }: { action: Action }) {
  return (
    <Link
      href={action.href}
      className="group flex flex-col rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-5 transition hover:border-[var(--rf-accent)] hover:shadow-sm"
    >
      <span className="text-base font-semibold transition group-hover:text-[var(--rf-accent)]">
        {action.label}
      </span>
      <span className="mt-2 text-sm leading-relaxed text-[var(--rf-muted)]">
        {action.description}
      </span>
    </Link>
  );
}

function SectionHeading({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div className="mb-8">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--rf-accent)]">
        {eyebrow}
      </p>
      <h2 className="rf-display mt-2 text-3xl md:text-4xl">{title}</h2>
    </div>
  );
}

export default function HomePage() {
  return (
    <div>
      <section className="rf-hero-bg relative overflow-hidden border-b border-[var(--rf-border)]">
        <div className="rf-animate-rise mx-auto max-w-4xl px-4 py-24 text-center md:py-32">
          <p className="rf-display text-5xl leading-none md:text-7xl">ResearchForge</p>
          <h1 className="mx-auto mt-6 max-w-2xl text-2xl font-medium leading-snug md:text-4xl">
            Draft manuscripts grounded in your evidence — not guesswork.
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-[var(--rf-muted)] md:text-lg">
            Start from a question, a paper, or a dataset. ResearchForge helps you outline, draft,
            cite and export — with every claim traceable to a source you provided.
          </p>
          <div className="mt-9 flex flex-wrap justify-center gap-3">
            <Link href="/workspace">
              <Button size="lg">Open guest workspace</Button>
            </Link>
            <Link href="/register">
              <Button size="lg" variant="secondary">
                Create account
              </Button>
            </Link>
          </div>
          <p className="mt-5 text-sm text-[var(--rf-muted)]">
            No account needed to try it. Nothing leaves your browser until you sign in.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-20">
        <SectionHeading eyebrow="Start with your research" title="Pick up wherever you are" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {startActions.map((action) => (
            <ActionCard key={action.label} action={action} />
          ))}
        </div>
      </section>

      <section className="border-y border-[var(--rf-border)] bg-[var(--rf-surface-2)]">
        <div className="mx-auto max-w-6xl px-4 py-20">
          <SectionHeading
            eyebrow="Work with evidence and sources"
            title="Everything tied back to what you uploaded"
          />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {capabilities.map((action) => (
              <ActionCard key={action.label} action={action} />
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-20">
        <SectionHeading eyebrow="How it works" title="Three steps, start to submission" />
        <ol className="grid gap-8 md:grid-cols-3">
          {steps.map((step) => (
            <li key={step.number}>
              <p className="rf-display text-4xl text-[var(--rf-accent)]">{step.number}</p>
              <h3 className="mt-3 text-lg font-semibold">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--rf-muted)]">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-t border-[var(--rf-border)] bg-[var(--rf-surface-2)]">
        <div className="mx-auto max-w-3xl px-4 py-20 text-center">
          <h2 className="rf-display text-3xl md:text-4xl">Ready to draft something?</h2>
          <p className="mx-auto mt-4 max-w-xl text-[var(--rf-muted)]">
            Open the guest workspace to try it in your browser, or create an account to save
            projects, upload files and export full manuscripts.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/workspace">
              <Button size="lg">Open guest workspace</Button>
            </Link>
            <Link href="/pricing">
              <Button size="lg" variant="secondary">
                See plans
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
