import type { Metadata } from 'next';
import Link from 'next/link';
import { Button } from '@researchforge/ui';

export const metadata: Metadata = {
  title: 'Pricing',
};

const tiers = [
  {
    name: 'Guest',
    price: 'Free',
    detail: 'Limited preview in the browser. No server-side saves or full exports.',
  },
  {
    name: 'Researcher',
    price: 'Coming soon',
    detail: 'Autosave, private projects, files, datasets, figures, and journal exports.',
  },
  {
    name: 'Lab',
    price: 'Coming soon',
    detail: 'Shared workspaces and admin controls for research groups.',
  },
];

export default function PricingPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-16">
      <h1 className="rf-display text-4xl">Pricing</h1>
      <p className="mt-3 max-w-2xl text-[var(--rf-muted)]">
        Placeholder plans for the foundation release. Guests explore freely; paid plans unlock
        durable project storage and collaboration.
      </p>
      <div className="mt-10 grid gap-6 md:grid-cols-3">
        {tiers.map((tier) => (
          <article
            key={tier.name}
            className="rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-5"
          >
            <h2 className="text-xl font-semibold">{tier.name}</h2>
            <p className="mt-2 text-2xl">{tier.price}</p>
            <p className="mt-3 text-sm text-[var(--rf-muted)]">{tier.detail}</p>
          </article>
        ))}
      </div>
      <div className="mt-8">
        <Link href="/workspace">
          <Button>Try the guest workspace</Button>
        </Link>
      </div>
    </div>
  );
}
