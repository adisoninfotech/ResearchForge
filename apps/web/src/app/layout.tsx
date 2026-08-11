import type { Metadata } from 'next';
import { Fraunces, Source_Sans_3 } from 'next/font/google';
import type { CSSProperties, ReactNode } from 'react';
import { ErrorBoundary } from '@/components/error-boundary';
import { Providers } from '@/components/providers';
import { SiteFooter } from '@/components/site-footer';
import { SiteHeader } from '@/components/site-header';
import './globals.css';

const display = Fraunces({
  subsets: ['latin'],
  variable: '--font-display-loaded',
});

const sans = Source_Sans_3({
  subsets: ['latin'],
  variable: '--font-sans-loaded',
});

export const metadata: Metadata = {
  title: {
    default: 'ResearchForge',
    template: '%s · ResearchForge',
  },
  description:
    'Evidence-grounded research manuscripts, references, datasets, figures, and journal-ready exports.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${display.variable} ${sans.variable}`}>
      <body
        style={
          {
            '--font-display': 'var(--font-display-loaded), Georgia, serif',
            '--font-sans': 'var(--font-sans-loaded), "Segoe UI", sans-serif',
          } as CSSProperties
        }
      >
        <Providers>
          <ErrorBoundary>
            <a
              href="#main"
              className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-[var(--rf-accent)] focus:px-3 focus:py-2 focus:text-[var(--rf-accent-fg)]"
            >
              Skip to content
            </a>
            <SiteHeader />
            <main id="main">{children}</main>
            <SiteFooter />
          </ErrorBoundary>
        </Providers>
      </body>
    </html>
  );
}
