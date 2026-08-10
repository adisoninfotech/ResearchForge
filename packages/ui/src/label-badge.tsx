import type { ReactNode } from 'react';
import { cn } from './cn';

export function SyntheticDataBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded border border-amber-700/40 bg-amber-100 px-2 py-0.5',
        'text-xs font-semibold uppercase tracking-wide text-amber-950 dark:bg-amber-950/40 dark:text-amber-100',
        className,
      )}
    >
      Synthetic / simulated
    </span>
  );
}

const NOTICE_TONES: Record<string, string> = {
  info: 'border-[var(--rf-border)] bg-[var(--rf-surface-2)] text-[var(--rf-muted)]',
  warning:
    'border-amber-700/40 bg-amber-50 text-amber-950 dark:bg-amber-950/30 dark:text-amber-100',
  danger: 'border-red-700/40 bg-red-50 text-red-950 dark:bg-red-950/30 dark:text-red-100',
};

export function Notice({
  children,
  className,
  tone = 'info',
}: {
  children: ReactNode;
  className?: string;
  tone?: 'info' | 'warning' | 'danger';
}) {
  return (
    <p
      role="note"
      className={cn(
        'rounded-md border px-3 py-2 text-sm',
        NOTICE_TONES[tone] ?? NOTICE_TONES.info,
        className,
      )}
    >
      {children}
    </p>
  );
}
