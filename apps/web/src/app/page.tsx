import Link from 'next/link';
import { Button } from '@researchforge/ui';

export default function HomePage() {
  return (
    <div className="rf-hero-bg relative overflow-hidden">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl items-center gap-10 px-4 py-16 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rf-animate-rise space-y-6">
          <p className="rf-display text-5xl leading-none tracking-tight md:text-7xl">
            ResearchForge
          </p>
          <h1 className="max-w-xl text-2xl font-medium leading-snug md:text-3xl">
            Draft manuscripts grounded in your evidence—not guesswork.
          </h1>
          <p className="max-w-lg text-[var(--rf-muted)]">
            Explore as a guest with a browser-local preview. Sign in to save projects, upload files,
            export complete manuscripts, and run full similarity checks.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/workspace">
              <Button size="lg">Open guest workspace</Button>
            </Link>
            <Link href="/register">
              <Button size="lg" variant="secondary">
                Create account
              </Button>
            </Link>
          </div>
        </div>
        <div
          aria-hidden="true"
          className="rf-animate-drift relative hidden h-[28rem] rounded-none border-y border-[var(--rf-border)] bg-[url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22800%22 height=%22600%22 viewBox=%220 0 800 600%22%3E%3Crect fill=%22%230f6a56%22 width=%22800%22 height=%22600%22/%3E%3Cpath fill=%22%23d9efe4%22 opacity=%220.25%22 d=%22M0 420C120 360 220 500 360 460C520 410 620 280 800 320V600H0Z%22/%3E%3Cpath fill=%22%23f0e2c8%22 opacity=%220.35%22 d=%22M0 0H800V180C620 220 500 120 340 150C180 180 80 260 0 220Z%22/%3E%3C/svg%3E')] bg-cover bg-center lg:block"
        />
      </div>
    </div>
  );
}
