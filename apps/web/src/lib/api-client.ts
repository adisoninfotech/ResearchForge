import type {
  AIJob,
  AIProposal,
  AuthResponse,
  ClaimProvenancePublic,
  CompletenessTemplateItem,
  EvidenceLinkPublic,
  EvidencePassage,
  GuestOutlineResponse,
  GuestTransferResponse,
  Manuscript,
  ManuscriptSection,
  ManuscriptVersion,
  ProjectFact,
  ProjectFilePublic,
  ProjectPublic,
  ReferencePublic,
  SessionPublic,
  UserPublic,
} from '@researchforge/shared-types';
import { clearCsrfToken, readCsrfToken, storeCsrfToken } from './csrf';
import { getApiBaseUrl, getPublicEnv } from './env';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public requestId?: string | null,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let message = response.statusText;
  let code: string | undefined;
  let details: Record<string, unknown> = {};
  let requestId: string | null | undefined = response.headers.get('X-Request-ID');
  try {
    const body = (await response.json()) as {
      error?: {
        message?: string;
        code?: string;
        request_id?: string;
        details?: Record<string, unknown>;
      };
    };
    if (body.error?.message) message = body.error.message;
    code = body.error?.code;
    details = body.error?.details ?? {};
    requestId = body.error?.request_id ?? requestId;
  } catch {
    // non-JSON error body is fine; keep statusText
  }
  return new ApiError(message, response.status, code, requestId, details);
}

async function request<T>(path: string, init?: RequestInit & { csrf?: boolean }): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (init?.csrf) {
    const csrf = readCsrfToken();
    if (csrf) headers['X-CSRF-Token'] = csrf;
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    credentials: 'include',
    headers,
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export interface GuestOutlinePayload {
  title: string;
  research_area: string;
  target_format: string;
  research_problem: string;
  proposed_contribution: string;
}

export const api = {
  healthLive: async () => {
    const origin = getPublicEnv().NEXT_PUBLIC_API_URL.replace(/\/$/, '');
    const response = await fetch(`${origin}/health/live`);
    if (!response.ok) throw await parseError(response);
    return response.json() as Promise<{ status: string; service: string }>;
  },
  register: async (body: {
    email: string;
    password: string;
    display_name?: string;
    training_opt_in?: boolean;
    device_name?: string;
  }) => {
    const result = await request<AuthResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    storeCsrfToken(result.csrf_token);
    return result;
  },
  login: async (body: {
    email: string;
    password: string;
    remember_me?: boolean;
    device_name?: string;
  }) => {
    const result = await request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    storeCsrfToken(result.csrf_token);
    return result;
  },
  logout: async () => {
    const result = await request<{ message: string }>('/auth/logout', {
      method: 'POST',
      csrf: true,
    });
    clearCsrfToken();
    return result;
  },
  refresh: async () => {
    const result = await request<AuthResponse>('/auth/refresh', { method: 'POST' });
    storeCsrfToken(result.csrf_token);
    return result;
  },
  me: () => request<UserPublic>('/auth/me'),
  verifyEmail: (token: string) =>
    request<{ message: string }>('/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),
  forgotPassword: (email: string) =>
    request<{ message: string }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, new_password: string) =>
    request<{ message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password }),
    }),
  oauthStatus: () =>
    request<{ google_enabled: boolean; google_authorization_url: string | null }>(
      '/auth/oauth/status',
    ),
  updateAccount: (body: { display_name?: string; training_opt_in?: boolean }) =>
    request<UserPublic>('/account/me', {
      method: 'PATCH',
      csrf: true,
      body: JSON.stringify(body),
    }),
  listSessions: () => request<SessionPublic[]>('/account/sessions'),
  revokeSession: (sessionId: string) =>
    request<{ message: string }>(`/account/sessions/${sessionId}/revoke`, {
      method: 'POST',
      csrf: true,
    }),
  revokeOtherSessions: () =>
    request<{ message: string }>('/account/sessions/revoke-others', {
      method: 'POST',
      csrf: true,
    }),
  deleteAccount: (password: string) =>
    request<{ message: string }>('/account/delete', {
      method: 'POST',
      csrf: true,
      body: JSON.stringify({ password, confirmation: 'DELETE' }),
    }),
  guestOutline: (body: GuestOutlinePayload) =>
    request<GuestOutlineResponse>('/guest/outline', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  convertGuestDraft: (body: Record<string, unknown>) =>
    request<GuestTransferResponse>('/projects/from-guest', {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  listProjects: (params?: { status?: string; q?: string; sort?: string }) => {
    const sp = new URLSearchParams();
    if (params?.status) sp.set('status', params.status);
    if (params?.q) sp.set('q', params.q);
    if (params?.sort) sp.set('sort', params.sort);
    const qs = sp.toString();
    return request<ProjectPublic[]>(`/projects${qs ? `?${qs}` : ''}`);
  },
  createProject: (body: Record<string, unknown>) =>
    request<ProjectPublic>('/projects', {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  getProject: (id: string) => request<ProjectPublic>(`/projects/${id}`),
  updateProject: (id: string, body: Record<string, unknown>) =>
    request<ProjectPublic>(`/projects/${id}`, {
      method: 'PATCH',
      csrf: true,
      body: JSON.stringify(body),
    }),
  trashProject: (id: string) =>
    request<ProjectPublic>(`/projects/${id}/trash`, { method: 'POST', csrf: true }),
  restoreProject: (id: string) =>
    request<ProjectPublic>(`/projects/${id}/restore`, { method: 'POST', csrf: true }),
  emptyTrash: () =>
    request<{ purged: number }>('/projects/trash/empty', { method: 'POST', csrf: true }),
  permanentDelete: (id: string) =>
    request<{ purged: boolean }>(`/projects/${id}/permanent-delete`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify({ confirmation: 'DELETE' }),
    }),
  getManuscript: (projectId: string) => request<Manuscript>(`/projects/${projectId}/manuscript`),
  saveSection: (
    projectId: string,
    sectionId: string,
    body: {
      structured_content: Record<string, unknown>;
      expected_revision: number;
      title?: string;
      create_snapshot?: boolean;
      snapshot_summary?: string;
      reason?: string;
    },
    etag?: string,
  ) =>
    request<{
      section: ManuscriptSection;
      completion_percent: number;
      last_activity_at: string | null;
    }>(`/projects/${projectId}/sections/${sectionId}`, {
      method: 'PUT',
      csrf: true,
      headers: etag ? { 'If-Match': etag } : undefined,
      body: JSON.stringify(body),
    }),
  reorderSections: (projectId: string, ordered_section_ids: string[]) =>
    request<{ sections: ManuscriptSection[] }>(`/projects/${projectId}/sections/reorder`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify({ ordered_section_ids }),
    }),
  addCustomSection: (projectId: string, title: string) =>
    request<{ section: ManuscriptSection }>(`/projects/${projectId}/sections`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify({ title }),
    }),
  listVersions: (projectId: string) =>
    request<ManuscriptVersion[]>(`/projects/${projectId}/versions`),
  getVersion: (projectId: string, versionId: string) =>
    request<ManuscriptVersion>(`/projects/${projectId}/versions/${versionId}`),
  createNamedVersion: (projectId: string, change_summary: string) =>
    request<ManuscriptVersion>(`/projects/${projectId}/versions`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify({ change_summary }),
    }),
  restoreVersion: (projectId: string, versionId: string) =>
    request<{ version: ManuscriptVersion; manuscript: Manuscript }>(
      `/projects/${projectId}/versions/${versionId}/restore`,
      { method: 'POST', csrf: true },
    ),
  compareVersions: (projectId: string, fromId: string, toId: string) =>
    request<{
      from_version: number;
      to_version: number;
      unified_diff: string[];
      from_text: string;
      to_text: string;
    }>(`/projects/${projectId}/versions/compare?from_version_id=${fromId}&to_version_id=${toId}`),
  listFacts: (projectId: string) =>
    request<{ template: CompletenessTemplateItem[]; facts: ProjectFact[] }>(
      `/projects/${projectId}/facts`,
    ),
  upsertFact: (
    projectId: string,
    body: { category: string; key: string; value: unknown; verification_status?: string },
  ) =>
    request<{ fact: ProjectFact }>(`/projects/${projectId}/facts`, {
      method: 'PUT',
      csrf: true,
      body: JSON.stringify(body),
    }),
  aiHealth: () => request<{ provider: string; healthy: boolean; model: string }>('/ai/health'),
  aiGenerate: (body: Record<string, unknown>) =>
    request<AIJob>('/ai/generate', {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  aiJob: (jobId: string) => request<AIJob>(`/ai/jobs/${jobId}`),
  aiCancel: (jobId: string) =>
    request<AIJob>(`/ai/jobs/${jobId}/cancel`, { method: 'POST', csrf: true }),
  aiProposal: (proposalId: string) => request<AIProposal>(`/ai/proposals/${proposalId}`),
  aiAcceptProposal: (proposalId: string, accepted_text?: string) =>
    request<{ id: string; status: string; accepted_text: string | null }>(
      `/ai/proposals/${proposalId}/accept`,
      {
        method: 'POST',
        csrf: true,
        body: JSON.stringify({ accepted_text: accepted_text ?? null }),
      },
    ),
  aiRejectProposal: (proposalId: string) =>
    request<{ id: string; status: string }>(`/ai/proposals/${proposalId}/reject`, {
      method: 'POST',
      csrf: true,
    }),
  authorizeUpload: (projectId: string) =>
    request<{
      authorized: boolean;
      max_bytes: number;
      allowed_content_types: string[];
      upload_path: string;
    }>(`/projects/${projectId}/files/authorize`, { method: 'POST', csrf: true }),
  listFiles: (projectId: string) => request<ProjectFilePublic[]>(`/projects/${projectId}/files`),
  uploadFile: async (projectId: string, file: File) => {
    const headers: Record<string, string> = { Accept: 'application/json' };
    const csrf = readCsrfToken();
    if (csrf) headers['X-CSRF-Token'] = csrf;
    const body = new FormData();
    body.append('file', file);
    body.append('process_sync', 'false');
    const response = await fetch(`${getApiBaseUrl()}/projects/${projectId}/files/upload`, {
      method: 'POST',
      credentials: 'include',
      headers,
      body,
    });
    if (!response.ok) throw await parseError(response);
    return (await response.json()) as ProjectFilePublic;
  },
  patchFile: (projectId: string, fileId: string, body: { exclude_from_ai?: boolean }) =>
    request<ProjectFilePublic>(`/projects/${projectId}/files/${fileId}`, {
      method: 'PATCH',
      csrf: true,
      body: JSON.stringify(body),
    }),
  searchEvidence: (projectId: string, query: string, limit = 10) =>
    request<{ results: EvidencePassage[] }>(`/projects/${projectId}/search`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify({ query, limit }),
    }),
  listReferences: (projectId: string, q?: string) => {
    const qs = q ? `?q=${encodeURIComponent(q)}` : '';
    return request<ReferencePublic[]>(`/projects/${projectId}/references${qs}`);
  },
  importReferences: (projectId: string, text: string, format: 'bibtex' | 'ris') =>
    request<{ references: ReferencePublic[] }>(`/projects/${projectId}/references/import`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify({ text, format }),
    }),
  listEvidence: (projectId: string, sectionId?: string) => {
    const qs = sectionId ? `?section_id=${sectionId}` : '';
    return request<EvidenceLinkPublic[]>(`/projects/${projectId}/evidence${qs}`);
  },
  pinEvidence: (
    projectId: string,
    body: {
      chunk_id: string;
      section_id?: string | null;
      relation: string;
      note?: string | null;
    },
  ) =>
    request<{ id: string; chunk_id: string; relation: string; note: string | null }>(
      `/projects/${projectId}/evidence`,
      { method: 'POST', csrf: true, body: JSON.stringify(body) },
    ),
  removeEvidence: (projectId: string, linkId: string) =>
    request<{ status: string }>(`/projects/${projectId}/evidence/${linkId}`, {
      method: 'DELETE',
      csrf: true,
    }),
  listClaims: (projectId: string, sectionId?: string) => {
    const qs = sectionId ? `?section_id=${sectionId}` : '';
    return request<ClaimProvenancePublic[]>(`/projects/${projectId}/claims${qs}`);
  },
  datasetLimitations: (projectId: string) =>
    request<{ limitations: string[] }>(`/projects/${projectId}/datasets/limitations`),
  listDatasets: (projectId: string) =>
    request<Record<string, unknown>[]>(`/projects/${projectId}/datasets`),
  uploadDataset: async (projectId: string, file: File, name?: string) => {
    const headers: Record<string, string> = { Accept: 'application/json' };
    const csrf = readCsrfToken();
    if (csrf) headers['X-CSRF-Token'] = csrf;
    const body = new FormData();
    body.append('file', file);
    if (name) body.append('name', name);
    body.append('provenance_type', 'uploaded_real');
    const response = await fetch(`${getApiBaseUrl()}/projects/${projectId}/datasets/upload`, {
      method: 'POST',
      credentials: 'include',
      headers,
      body,
    });
    if (!response.ok) throw await parseError(response);
    return (await response.json()) as Record<string, unknown>;
  },
  createSyntheticDataset: (projectId: string, body: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/projects/${projectId}/datasets/synthetic`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  deleteDataset: (projectId: string, datasetId: string) =>
    request<{ status: string }>(`/projects/${projectId}/datasets/${datasetId}`, {
      method: 'DELETE',
      csrf: true,
    }),
  runAnalysis: (projectId: string, body: Record<string, unknown>) =>
    request<{ id: string; status: string; results: Record<string, unknown> | null }>(
      `/projects/${projectId}/analyses`,
      { method: 'POST', csrf: true, body: JSON.stringify(body) },
    ),
  createFigure: (projectId: string, body: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/projects/${projectId}/figures`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  listFigures: (projectId: string) =>
    request<Record<string, unknown>[]>(`/projects/${projectId}/figures`),
  createTable: (projectId: string, body: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/projects/${projectId}/tables`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  listTables: (projectId: string) =>
    request<Record<string, unknown>[]>(`/projects/${projectId}/tables`),
  insertManuscriptAsset: (
    projectId: string,
    body: { section_id: string; asset_type: string; asset_stable_id: string },
  ) =>
    request<Record<string, unknown>>(`/projects/${projectId}/manuscript-assets/insert`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  similarityMeta: (projectId: string) =>
    request<{
      language: { safe_summary: string; forbidden_claims: string[] };
      coverage_limitations: string[];
      threshold_profiles: Record<string, unknown>;
    }>(`/projects/${projectId}/similarity/meta`),
  runSimilarity: (projectId: string, body: Record<string, unknown>) =>
    request<{
      id: string;
      status: string;
      report_id: string | null;
      report?: Record<string, unknown>;
    }>(`/projects/${projectId}/similarity/run`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  getSimilarityReport: (
    projectId: string,
    reportId: string,
    params?: {
      exclude_bibliography?: boolean;
      exclude_quotations?: boolean;
      exclude_common?: boolean;
      classification?: string;
    },
  ) => {
    const sp = new URLSearchParams();
    if (params?.exclude_bibliography) sp.set('exclude_bibliography', 'true');
    if (params?.exclude_quotations) sp.set('exclude_quotations', 'true');
    if (params?.exclude_common) sp.set('exclude_common', 'true');
    if (params?.classification) sp.set('classification', params.classification);
    const qs = sp.toString();
    return request<Record<string, unknown>>(
      `/projects/${projectId}/similarity/reports/${reportId}${qs ? `?${qs}` : ''}`,
    );
  },
  downloadSimilarityReport: async (projectId: string, reportId: string) => {
    const response = await fetch(
      `${getApiBaseUrl()}/projects/${projectId}/similarity/reports/${reportId}/download`,
      { credentials: 'include' },
    );
    if (!response.ok) throw await parseError(response);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `similarity-report-${reportId}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  },
  resolveSimilarityFinding: (
    projectId: string,
    findingId: string,
    body: { action: string; note?: string },
  ) =>
    request<Record<string, unknown>>(
      `/projects/${projectId}/similarity/findings/${findingId}/resolve`,
      { method: 'POST', csrf: true, body: JSON.stringify(body) },
    ),
  proposeSimilarityRewrite: (projectId: string, findingId: string) =>
    request<Record<string, unknown>>(
      `/projects/${projectId}/similarity/findings/${findingId}/rewrite`,
      { method: 'POST', csrf: true },
    ),
  acceptSimilarityRewrite: (projectId: string, findingId: string, accepted_text?: string) =>
    request<Record<string, unknown>>(
      `/projects/${projectId}/similarity/findings/${findingId}/rewrite/accept`,
      {
        method: 'POST',
        csrf: true,
        body: JSON.stringify({ accepted_text: accepted_text ?? null }),
      },
    ),
  exportMeta: (projectId: string) =>
    request<{
      templates: Array<{
        id: string;
        name: string;
        version: string;
        description: string;
        warning: string;
      }>;
      template_warning: string;
      outputs: string[];
      pdf_available: boolean;
      guest_restriction: string;
      certification_note: string;
    }>(`/projects/${projectId}/exports/meta`),
  exportPreview: (projectId: string, body: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/projects/${projectId}/exports/preview`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  runExport: (projectId: string, body: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/projects/${projectId}/exports/run`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  listExportJobs: (projectId: string) =>
    request<{ jobs: Record<string, unknown>[] }>(`/projects/${projectId}/exports/jobs`),
  exportHistory: (projectId: string) =>
    request<{ downloads: Record<string, unknown>[] }>(`/projects/${projectId}/exports/history`),
  downloadExportArtifact: async (projectId: string, artifactId: string) => {
    const grant = await request<{
      download_token: string;
      download_path: string;
      artifact: { filename: string };
    }>(`/projects/${projectId}/exports/artifacts/${artifactId}/download`, {
      method: 'POST',
      csrf: true,
    });
    const response = await fetch(`${getApiBaseUrl()}/exports/download/${grant.download_token}`, {
      credentials: 'include',
    });
    if (!response.ok) throw await parseError(response);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = grant.artifact.filename || 'export.bin';
    a.click();
    URL.revokeObjectURL(url);
  },
  engagementHome: (projectId: string) =>
    request<Record<string, unknown>>(`/projects/${projectId}/engagement/home`),
  engagementProgress: (projectId: string) =>
    request<Record<string, unknown>>(`/projects/${projectId}/engagement/progress`),
  setDailyGoal: (projectId: string, body: { goal_type: string; goal_date?: string }) =>
    request<Record<string, unknown>>(`/projects/${projectId}/engagement/goals`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  completeGoalStep: (projectId: string, body: { step_id: string }) =>
    request<Record<string, unknown>>(`/projects/${projectId}/engagement/goals/steps`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  answerGuidedQuestion: (
    projectId: string,
    body: { category: string; key: string; value: unknown },
  ) =>
    request<Record<string, unknown>>(`/projects/${projectId}/engagement/questions/answer`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  retentionAction: (projectId: string, body: { action: string; confirmation?: string }) =>
    request<Record<string, unknown>>(`/projects/${projectId}/engagement/retention/actions`, {
      method: 'POST',
      csrf: true,
      body: JSON.stringify(body),
    }),
  getNotificationPreferences: () =>
    request<{
      preferences: Record<string, boolean>;
      labels: Record<string, string>;
      note: string;
    }>('/account/notifications/preferences'),
  updateNotificationPreferences: (preferences: Record<string, boolean>) =>
    request<Record<string, unknown>>('/account/notifications/preferences', {
      method: 'PUT',
      csrf: true,
      body: JSON.stringify({ preferences }),
    }),
};
