import type { TextareaHTMLAttributes } from 'react';
import { cn } from './cn';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  error?: string;
}

export function Textarea({ label, error, id, className, ...props }: TextareaProps) {
  const inputId = id ?? props.name ?? label.toLowerCase().replace(/\s+/g, '-');
  const errorId = `${inputId}-error`;
  return (
    <label className="flex w-full flex-col gap-1.5 text-sm" htmlFor={inputId}>
      <span className="font-medium text-[var(--rf-fg)]">{label}</span>
      <textarea
        id={inputId}
        className={cn(
          'min-h-28 rounded-md border border-[var(--rf-border)] bg-[var(--rf-surface)] px-3 py-2',
          'text-[var(--rf-fg)] placeholder:text-[var(--rf-muted)]',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--rf-accent)]',
          error && 'border-[var(--rf-danger)]',
          className,
        )}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : undefined}
        {...props}
      />
      {error ? (
        <span id={errorId} className="text-[var(--rf-danger)]" role="alert">
          {error}
        </span>
      ) : null}
    </label>
  );
}
