import type { Metadata } from 'next';
import { ContactForm } from '@/components/contact-form';

export const metadata: Metadata = {
  title: 'Contact us',
  description: 'Get in touch with the ResearchForge team about access, plans, or your research.',
};

export default function ContactPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <header className="text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--rf-accent)]">
          Get in touch
        </p>
        <h1 className="rf-display mt-2 text-4xl md:text-5xl">Contact us</h1>
        <p className="mx-auto mt-4 max-w-xl text-[var(--rf-muted)]">
          Questions about ResearchForge, institutional access, or the Lab plan? Send us a message
          and we&rsquo;ll reply to the address you give us.
        </p>
      </header>

      <div className="mt-10">
        {/* Same component the landing page section uses — one form to maintain. */}
        <ContactForm />
      </div>

      <p className="mt-10 text-center text-sm text-[var(--rf-muted)]">An Adison Infotech product</p>
    </div>
  );
}
