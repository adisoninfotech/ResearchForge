'use client';

import type { CompletenessTemplateItem, ProjectFact } from '@researchforge/shared-types';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api-client';

interface CompletenessPanelProps {
  projectId: string;
}

export function CompletenessPanel({ projectId }: CompletenessPanelProps) {
  const [template, setTemplate] = useState<CompletenessTemplateItem[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);

  useEffect(() => {
    void api.listFacts(projectId).then((res) => {
      setTemplate(res.template);
      const map: Record<string, string> = {};
      for (const fact of res.facts) {
        map[`${fact.category}:${fact.key}`] = stringifyValue(fact.value);
      }
      setValues(map);
    });
  }, [projectId]);

  async function save(item: CompletenessTemplateItem, value: string) {
    const key = `${item.category}:${item.key}`;
    setSavingKey(key);
    try {
      const { fact } = await api.upsertFact(projectId, {
        category: item.category,
        key: item.key,
        value: value.trim() || null,
      });
      setValues((prev) => ({ ...prev, [key]: stringifyValue(fact.value) }));
    } finally {
      setSavingKey(null);
    }
  }

  const filled = template.filter((t) => (values[`${t.category}:${t.key}`] || '').trim()).length;

  return (
    <aside className="space-y-4 rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-4">
      <div>
        <h2 className="rf-display text-xl">Research completeness</h2>
        <p className="text-xs text-[var(--rf-muted)]">
          {filled}/{template.length} fields captured
        </p>
      </div>
      <ul className="space-y-3">
        {template.map((item) => {
          const key = `${item.category}:${item.key}`;
          return (
            <li key={key} className="space-y-1">
              <label className="block text-xs font-medium" htmlFor={key}>
                {item.label}
              </label>
              <textarea
                id={key}
                className="w-full rounded-md border border-[var(--rf-border)] bg-[var(--rf-bg)] px-2 py-1.5 text-sm"
                rows={2}
                value={values[key] || ''}
                onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
                onBlur={(e) => void save(item, e.target.value)}
              />
              {savingKey === key ? (
                <p className="text-[10px] text-[var(--rf-muted)]">Saving…</p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </aside>
  );
}

function stringifyValue(value: ProjectFact['value']): string {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}
