'use client';

import { Button, Notice } from '@researchforge/ui';
import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api-client';

const SAFE = 'No significant textual overlap was identified within the sources checked.';

interface SimilarityPanelProps {
  projectId: string;
  sectionId: string | null;
}

interface Finding {
  id: string;
  classification: string;
  manuscript_text: string;
  source_text: string;
  explanation: string;
  recommended_action: string;
  methods: string[];
  scores: Record<string, number>;
  citation_present: boolean;
  resolution?: {
    action: string;
    rewrite_proposed?: string | null;
    rewrite_diff?: Array<{ op: string; original: string; proposed: string }> | null;
  } | null;
}

interface Report {
  id: string;
  summary_text: string;
  risk_level: string;
  section_summaries: Array<{
    section_id: string;
    title: string;
    finding_count: number;
    risk_level: string;
  }>;
  findings: Finding[];
  coverage?: {
    sources_checked: Array<{ label: string; kind: string }>;
    sources_not_checked: Array<{ label?: string; reason?: string }>;
    limitations: string[];
    licensed_provider_status: string;
  };
  footer: Record<string, unknown>;
  method_explanations: Record<string, string>;
}

export function SimilarityPanel({ projectId, sectionId }: SimilarityPanelProps) {
  const [report, setReport] = useState<Report | null>(null);
  const [selected, setSelected] = useState<Finding | null>(null);
  const [excludeBib, setExcludeBib] = useState(true);
  const [excludeQuotes, setExcludeQuotes] = useState(false);
  const [excludeCommon, setExcludeCommon] = useState(true);
  const [filterClass, setFilterClass] = useState('');
  const [limitations, setLimitations] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void api.similarityMeta(projectId).then((meta) => {
      setLimitations(meta.coverage_limitations);
    });
  }, [projectId]);

  const refreshReport = useCallback(
    async (reportId: string) => {
      const r = (await api.getSimilarityReport(projectId, reportId, {
        exclude_bibliography: excludeBib,
        exclude_quotations: excludeQuotes,
        exclude_common: excludeCommon,
        classification: filterClass || undefined,
      })) as unknown as Report;
      setReport(r);
      setSelected(r.findings[0] ?? null);
    },
    [projectId, excludeBib, excludeQuotes, excludeCommon, filterClass],
  );

  async function runCheck() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.runSimilarity(projectId, {
        threshold_profile: 'default',
        exclude_bibliography: excludeBib,
        exclude_quotations: excludeQuotes,
        exclude_common_phrases: excludeCommon,
      });
      const reportPayload = result.report as unknown as Report | undefined;
      if (reportPayload) {
        setReport(reportPayload);
        setSelected(reportPayload.findings[0] ?? null);
      } else if (result.report_id) {
        await refreshReport(String(result.report_id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Similarity check failed');
    } finally {
      setBusy(false);
    }
  }

  const visibleFindings = report?.findings.filter((f) => !sectionId || !f || true) ?? [];

  return (
    <section className="space-y-4 rounded-lg border border-[var(--rf-border)] bg-[var(--rf-surface)] p-4">
      <div>
        <h2 className="rf-display text-xl">Similarity & citation risk</h2>
        <p className="text-xs text-[var(--rf-muted)]">
          Advisory overlap review within sources you can access. Not a plagiarism guarantee.
        </p>
      </div>

      <Notice>
        Never claims zero plagiarism, plagiarism-free status, guaranteed originality, or equivalence
        to Turnitin/iThenticate. Preferred clear finding: “{SAFE}”
      </Notice>

      {error ? <Notice>{error}</Notice> : null}

      <div className="flex flex-wrap gap-3 text-xs">
        <label className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={excludeBib}
            onChange={(e) => setExcludeBib(e.target.checked)}
          />
          Exclude bibliography
        </label>
        <label className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={excludeQuotes}
            onChange={(e) => setExcludeQuotes(e.target.checked)}
          />
          Exclude quotations
        </label>
        <label className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={excludeCommon}
            onChange={(e) => setExcludeCommon(e.target.checked)}
          />
          Exclude short/common phrases
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" disabled={busy} onClick={() => void runCheck()}>
          Run check
        </Button>
        {report ? (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => {
              void api.downloadSimilarityReport(projectId, report.id);
            }}
          >
            Download report
          </Button>
        ) : null}
      </div>

      {report ? (
        <div className="space-y-3 text-xs">
          <div>
            <p className="font-medium">Overall risk: {report.risk_level}</p>
            <p>{report.summary_text}</p>
          </div>

          <div className="border-t border-[var(--rf-border)] pt-2">
            <p className="font-medium">Section summary</p>
            <ul className="list-disc pl-4">
              {report.section_summaries.map((s) => (
                <li key={s.section_id}>
                  {s.title}: {s.finding_count} finding(s) ({s.risk_level})
                </li>
              ))}
            </ul>
          </div>

          <div className="border-t border-[var(--rf-border)] pt-2">
            <p className="font-medium">Coverage</p>
            <ul className="list-disc pl-4 text-[var(--rf-muted)]">
              {(report.coverage?.limitations || limitations).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <p className="mt-1">Checked:</p>
            <ul className="list-disc pl-4">
              {(report.coverage?.sources_checked || []).map((s) => (
                <li key={`${s.kind}-${s.label}`}>
                  {s.label} ({s.kind})
                </li>
              ))}
            </ul>
            <p className="mt-1">Not checked:</p>
            <ul className="list-disc pl-4">
              {(report.coverage?.sources_not_checked || []).map((s, idx) => (
                <li key={idx}>
                  {s.label}: {s.reason}
                </li>
              ))}
            </ul>
            <p className="mt-1 text-[var(--rf-muted)]">
              Licensed provider: {report.coverage?.licensed_provider_status}
            </p>
          </div>

          <div className="border-t border-[var(--rf-border)] pt-2">
            <label className="block font-medium">
              Filter classification{' '}
              <select
                className="ml-1 rounded border border-[var(--rf-border)] bg-[var(--rf-bg)]"
                value={filterClass}
                onChange={(e) => {
                  setFilterClass(e.target.value);
                  if (report) void refreshReport(report.id);
                }}
              >
                <option value="">All</option>
                {[
                  'exact_textual_overlap',
                  'near_textual_overlap',
                  'semantic_similarity',
                  'proper_quotation',
                  'citation_potentially_required',
                  'excessive_similarity_despite_citation',
                  'common_technical_phrase',
                  'self_overlap',
                  'internal_duplication',
                ].map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <ul className="mt-2 max-h-40 space-y-1 overflow-auto">
              {visibleFindings.map((f) => (
                <li key={f.id}>
                  <button
                    type="button"
                    className={`text-left underline ${selected?.id === f.id ? 'font-semibold' : ''}`}
                    onClick={() => setSelected(f)}
                  >
                    {f.classification}: {f.manuscript_text.slice(0, 60)}…
                  </button>
                </li>
              ))}
              {!visibleFindings.length ? <li>No findings under current filters.</li> : null}
            </ul>
          </div>

          {selected ? (
            <div className="space-y-2 border-t border-[var(--rf-border)] pt-2">
              <p className="font-medium">Side-by-side</p>
              <div className="grid gap-2 md:grid-cols-2">
                <pre className="whitespace-pre-wrap rounded border border-[var(--rf-border)] p-2">
                  Manuscript:{'\n'}
                  {selected.manuscript_text}
                </pre>
                <pre className="whitespace-pre-wrap rounded border border-[var(--rf-border)] p-2">
                  Source:{'\n'}
                  {selected.source_text}
                </pre>
              </div>
              <p>{selected.explanation}</p>
              <p className="text-[var(--rf-muted)]">Recommended: {selected.recommended_action}</p>
              <p className="text-[var(--rf-muted)]">
                Methods: {selected.methods.join(', ')} · Scores:{' '}
                {Object.entries(selected.scores)
                  .map(([k, v]) => `${k}=${typeof v === 'number' ? v.toFixed(2) : v}`)
                  .join(', ')}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    void api
                      .resolveSimilarityFinding(projectId, selected.id, {
                        action: 'false_positive',
                        note: 'Marked false positive by user',
                      })
                      .then((f) => setSelected(f as unknown as Finding));
                  }}
                >
                  Mark false positive
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    void api
                      .resolveSimilarityFinding(projectId, selected.id, {
                        action: 'accepted_technical_language',
                      })
                      .then((f) => setSelected(f as unknown as Finding));
                  }}
                >
                  Accept technical language
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    void api
                      .resolveSimilarityFinding(projectId, selected.id, {
                        action: 'added_citation',
                        note: 'User will add citation',
                      })
                      .then((f) => setSelected(f as unknown as Finding));
                  }}
                >
                  Add citation
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => {
                    void api.proposeSimilarityRewrite(projectId, selected.id).then((f) => {
                      setSelected(f as unknown as Finding);
                    });
                  }}
                >
                  Propose rewrite
                </Button>
              </div>
              {selected.resolution?.rewrite_proposed ? (
                <div className="space-y-2">
                  <p className="font-medium">Proposed rewrite (meaning-preserving, not evasion)</p>
                  <pre className="whitespace-pre-wrap rounded border border-[var(--rf-border)] p-2">
                    {selected.resolution.rewrite_proposed}
                  </pre>
                  {selected.resolution.rewrite_diff ? (
                    <ul className="text-[10px] text-[var(--rf-muted)]">
                      {selected.resolution.rewrite_diff.map((d, i) => (
                        <li key={i}>
                          {d.op}: “{d.original}” → “{d.proposed}”
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => {
                      void api
                        .acceptSimilarityRewrite(projectId, selected.id)
                        .then(() => runCheck());
                    }}
                  >
                    Accept rewrite & re-check
                  </Button>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="border-t border-[var(--rf-border)] pt-2 text-[10px] text-[var(--rf-muted)]">
            <p className="font-medium">Report footer</p>
            <p>{String(report.footer.disclaimer || '')}</p>
            <p>Profile: {String(report.footer.threshold_profile || '')}</p>
            <p>Algorithms: {JSON.stringify(report.footer.algorithm_versions || {})}</p>
          </div>
        </div>
      ) : null}
    </section>
  );
}
