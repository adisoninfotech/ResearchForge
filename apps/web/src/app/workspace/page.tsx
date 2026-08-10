import type { Metadata } from 'next';
import { GuestWorkspace } from '@/components/guest-workspace';

export const metadata: Metadata = {
  title: 'Guest workspace',
};

export default function WorkspacePage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <h1 className="rf-display text-4xl">Guest research workspace</h1>
      <p className="mt-2 max-w-2xl text-[var(--rf-muted)]">
        Generate a limited outline preview. Gated actions open authentication so you can save and
        continue later.
      </p>
      <div className="mt-8">
        <GuestWorkspace />
      </div>
    </div>
  );
}
