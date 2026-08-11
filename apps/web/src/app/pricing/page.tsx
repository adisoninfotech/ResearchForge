import type { Metadata } from 'next';
import Link from 'next/link';
import { Button } from '@researchforge/ui';

export const metadata: Metadata = {
  title: 'Pricing',
};

type Tier = {
  name: string;
  price: string;
  cadence?: string;
  detail: string;
  features: string[];
  cta: string;
  href: string;
  featured?: boolean;
};

// Confirmed 11 Aug 2026. Single source of truth for the advertised price —
// change it here, not in the tier list below.
const RESEARCHER_PRICE = '£12';

const tiers: Tier[] = [
  {
    name: 'Guest',
    price: 'Free',
    detail: 'Explore the workspace in your browser. Nothing is stored on our servers.',
    features: [
      'Browser-local drafting',
      'Outline generation',
      'Up to 6 sections per draft',
      'No account required',
    ],
    cta: 'Try the guest workspace',
    href: '/workspace',
  },
  {
    name: 'Researcher',
    price: RESEARCHER_PRICE,
    cadence: '/month',
    detail: 'For individual researchers writing and submitting their own work.',
    features: [
      'Saved projects with autosave',
      'File uploads and evidence indexing',
      'Datasets, figures and tables',
      'Similarity reports',
      'DOCX and PDF export',
    ],
    cta: 'Create account',
    href: '/register',
    featured: true,
  },
  {
    name: 'Lab',
    price: 'Contact us',
    detail: 'Shared workspaces and admin controls for research groups.',
    features: [
      'Everything in Researcher',
      'Shared team workspaces',
      'Admin and access controls',
      'Priority support',
    ],
    cta: 'Get in touch',
    href: 'mailto:info@adisoninfotech.co.uk?subject=ResearchForge%20Lab%20plan',
  },
];

export default function PricingPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-16">
      <div className="max-w-2xl">
        <h1 className="rf-display text-4xl md:text-5xl">Pricing</h1>
        <p className="mt-4 text-[var(--rf-muted)]">
          Start free in the browser. Upgrade when you need saved projects, your own sources, and
          full manuscript exports.
        </p>
      </div>

      <div className="mt-12 grid items-start gap-6 md:grid-cols-3">
        {tiers.map((tier) => (
          <article
            key={tier.name}
            className={
              tier.featured
                ? 'relative rounded-lg border-2 border-[var(--rf-accent)] bg-[var(--rf-surface)] p-6 shadow-sm'
                : 'relative rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-6'
            }
          >
            {tier.featured ? (
              <span className="absolute -top-3 left-6 rounded-full bg-[var(--rf-accent)] px-3 py-1 text-xs font-semibold text-[var(--rf-accent-fg)]">
                Most popular
              </span>
            ) : null}

            <h2 className="text-lg font-semibold">{tier.name}</h2>

            <p className="mt-3 flex items-baseline gap-1">
              <span className="rf-display text-4xl">{tier.price}</span>
              {tier.cadence ? (
                <span className="text-sm text-[var(--rf-muted)]">{tier.cadence}</span>
              ) : null}
            </p>

            <p className="mt-3 text-sm leading-relaxed text-[var(--rf-muted)]">{tier.detail}</p>

            <ul className="mt-5 space-y-2 border-t border-[var(--rf-border)] pt-5">
              {tier.features.map((feature) => (
                <li key={feature} className="flex gap-2 text-sm">
                  <span aria-hidden="true" className="text-[var(--rf-accent)]">
                    ✓
                  </span>
                  <span>{feature}</span>
                </li>
              ))}
            </ul>

            <div className="mt-6">
              <Link href={tier.href}>
                <Button className="w-full" variant={tier.featured ? 'primary' : 'secondary'}>
                  {tier.cta}
                </Button>
              </Link>
            </div>
          </article>
        ))}
      </div>

      <p className="mt-10 text-sm text-[var(--rf-muted)]">
        Similarity checks help you find overlap with the sources you supply. They do not guarantee
        zero plagiarism, and are not a substitute for your institution&rsquo;s own checks.
      </p>
    </div>
  );
}
