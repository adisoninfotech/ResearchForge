'use client';

import type { ManuscriptAuthor } from '@researchforge/shared-types';
import { MAX_PROJECT_AUTHORS } from '@researchforge/shared-types';
import { Button } from '@researchforge/ui';

interface AuthorsEditorProps {
  authors: ManuscriptAuthor[];
  disabled?: boolean;
  onChange: (authors: ManuscriptAuthor[]) => void;
}

function emptyAuthor(): ManuscriptAuthor {
  return { name: '', affiliation: '', email: '', corresponding: false };
}

export function AuthorsEditor({ authors, disabled, onChange }: AuthorsEditorProps) {
  const list = authors.length > 0 ? authors : [emptyAuthor()];

  function updateAt(index: number, patch: Partial<ManuscriptAuthor>) {
    const next = list.map((a, i) => (i === index ? { ...a, ...patch } : a));
    if (patch.corresponding === true) {
      for (let i = 0; i < next.length; i += 1) {
        if (i !== index) next[i] = { ...next[i]!, corresponding: false };
      }
    }
    onChange(next);
  }

  function addAuthor() {
    if (list.length >= MAX_PROJECT_AUTHORS) return;
    onChange([...list, emptyAuthor()]);
  }

  function removeAuthor(index: number) {
    const next = list.filter((_, i) => i !== index);
    if (next.length === 0) {
      onChange([emptyAuthor()]);
      return;
    }
    if (!next.some((a) => a.corresponding)) {
      next[0] = { ...next[0]!, corresponding: true };
    }
    onChange(next);
  }

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-slate-800">Authors</p>
        <p className="text-xs text-slate-500">
          {list.filter((a) => a.name.trim()).length}/{MAX_PROJECT_AUTHORS}
        </p>
      </div>
      <ul className="space-y-3">
        {list.map((author, index) => (
          <li key={index} className="space-y-1 rounded border border-slate-200 p-2">
            <label className="block text-xs text-slate-600">
              Name
              <input
                className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm"
                value={author.name}
                disabled={disabled}
                onChange={(e) => updateAt(index, { name: e.target.value })}
                placeholder="Full name"
              />
            </label>
            <label className="block text-xs text-slate-600">
              Affiliation
              <input
                className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm"
                value={author.affiliation ?? ''}
                disabled={disabled}
                onChange={(e) => updateAt(index, { affiliation: e.target.value })}
              />
            </label>
            <label className="block text-xs text-slate-600">
              Email
              <input
                type="email"
                className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm"
                value={author.email ?? ''}
                disabled={disabled}
                onChange={(e) => updateAt(index, { email: e.target.value })}
              />
            </label>
            <div className="flex items-center justify-between gap-2 pt-1">
              <label className="flex items-center gap-1.5 text-xs text-slate-700">
                <input
                  type="radio"
                  name="corresponding-author"
                  checked={Boolean(author.corresponding)}
                  disabled={disabled}
                  onChange={() => updateAt(index, { corresponding: true })}
                />
                Corresponding
              </label>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={disabled || list.length <= 1}
                onClick={() => removeAuthor(index)}
              >
                Remove
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <Button
        type="button"
        size="sm"
        variant="secondary"
        disabled={disabled || list.length >= MAX_PROJECT_AUTHORS}
        onClick={addAuthor}
      >
        Add author
      </Button>
    </div>
  );
}

export function sanitizeAuthorsForSave(authors: ManuscriptAuthor[]): ManuscriptAuthor[] {
  const cleaned = authors
    .map((a) => ({
      name: a.name.trim(),
      affiliation: a.affiliation?.trim() || null,
      email: a.email?.trim() || null,
      corresponding: Boolean(a.corresponding),
    }))
    .filter((a) => a.name.length > 0)
    .slice(0, MAX_PROJECT_AUTHORS);
  if (cleaned.length > 0 && !cleaned.some((a) => a.corresponding)) {
    cleaned[0]!.corresponding = true;
  }
  return cleaned;
}
