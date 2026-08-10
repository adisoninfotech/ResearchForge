/** Shared contracts between web and documentation of API shapes. */

export type TargetFormat = 'IEEE' | 'ACM' | 'APA' | 'Nature' | 'Custom';

export type ProjectStatus = 'draft' | 'active' | 'archived' | 'trash';
export type RetentionPolicy = 'keep' | 'trash_30' | 'inactive_draft_90' | 'plan_default';
export type SaveState = 'idle' | 'saving' | 'saved' | 'offline' | 'conflict' | 'error';

export type AIJobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface AIJob {
  id: string;
  project_id: string | null;
  operation: string;
  status: AIJobStatus | string;
  progress: number;
  progress_events: Array<{ at?: string; message?: string; progress?: number }>;
  result_payload: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  proposal_id: string | null;
  model_name: string | null;
  prompt_template_id: string | null;
  prompt_version: string | null;
}

export interface AIProposal {
  id: string;
  job_id: string;
  project_id: string;
  section_id: string | null;
  status: string;
  original_text: string;
  proposed_text: string;
  proposed_structured: Record<string, unknown> | null;
  model_metadata: Record<string, unknown> | null;
  accepted_text: string | null;
}

export interface GuestDraft {
  title: string;
  researchArea: string;
  targetFormat: TargetFormat | string;
  researchProblem: string;
  proposedContribution: string;
  outline: OutlineSection[];
  sectionContent: string;
  conversionKey: string;
  updatedAt: string;
}

export interface OutlineSection {
  title: string;
  summary: string;
}

export interface GuestOutlineResponse {
  outline: {
    title: string;
    sections: OutlineSection[];
    provider: string;
    model: string;
    is_preview: boolean;
    disclaimer: string;
  };
  storage_hint: string;
  gated_actions: string[];
}

export interface UserPublic {
  id: string;
  email: string;
  display_name: string | null;
  email_verified: boolean;
  training_opt_in: boolean;
  subscription_plan: string;
  status: string;
}

export interface AuthResponse {
  user: UserPublic;
  message: string;
  csrf_token?: string | null;
}

export interface SessionPublic {
  id: string;
  device_name: string | null;
  user_agent: string | null;
  remember_me: boolean;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  revoked_at: string | null;
  is_current: boolean;
}

export interface ManuscriptAuthor {
  name: string;
  affiliation?: string | null;
  email?: string | null;
  corresponding?: boolean;
}

export const MAX_PROJECT_AUTHORS = 6;

export interface ProjectPublic {
  id: string;
  title: string;
  slug: string;
  research_field: string | null;
  paper_type: string | null;
  target_publisher: string | null;
  target_template: string | null;
  target_word_count: number | null;
  intended_submission_date: string | null;
  research_problem: string | null;
  proposed_contribution: string | null;
  authors: ManuscriptAuthor[];
  status: ProjectStatus | string;
  retention_policy: RetentionPolicy | string;
  last_activity_at: string | null;
  trash_at: string | null;
  purge_after: string | null;
  legal_hold: boolean;
  ai_enabled: boolean;
  is_private: boolean;
  transferred_from_guest: boolean;
  contains_synthetic_data: boolean;
  guest_conversion_key: string | null;
  completion_percent: number;
  updated_at: string | null;
  created_at: string | null;
}

export interface GuestTransferResponse {
  project: ProjectPublic;
  created: boolean;
  message: string;
}

export interface ManuscriptSection {
  id: string;
  section_type: string;
  title: string;
  position: number;
  structured_content: Record<string, unknown>;
  plain_text: string;
  word_count: number;
  status: string;
  revision_number: number;
  updated_at: string;
  etag: string;
}

export interface Manuscript {
  id: string;
  project_id: string;
  current_version_id: string | null;
  schema_version: number;
  completion_percent: number;
  total_word_count: number;
  sections: ManuscriptSection[];
}

export interface ManuscriptVersion {
  id: string;
  manuscript_id: string;
  version_number: number;
  change_summary: string;
  created_by_type: 'user' | 'ai' | 'system' | string;
  created_by_user_id: string | null;
  model_metadata: Record<string, unknown> | null;
  is_named: boolean;
  created_at: string;
  snapshot?: {
    sections: Array<{
      id: string;
      section_type: string;
      title: string;
      plain_text: string;
      word_count: number;
    }>;
  };
}

export interface ProjectFact {
  id: string;
  category: string;
  key: string;
  value: unknown;
  source_type: string;
  verification_status: string;
  updated_at: string;
}

export interface CompletenessTemplateItem {
  category: string;
  key: string;
  label: string;
}

export interface ProjectFilePublic {
  id: string;
  project_id: string;
  original_filename: string;
  safe_filename: string;
  kind: string;
  detected_mime: string;
  size_bytes: number;
  status: string;
  error_message: string | null;
  exclude_from_ai: boolean;
  is_figure: boolean;
  created_at: string | null;
  download_url?: string;
  signed_url_expires_in?: number;
}

export interface EvidencePassage {
  chunk_id: string;
  evidence_key: string;
  text: string;
  source_file_id: string;
  page: number | null;
  section: string | null;
  char_start: number | null;
  char_end: number | null;
  reference_id: string | null;
  score: number;
  match_source: string;
}

export interface ReferencePublic {
  id: string;
  project_id: string;
  title: string | null;
  year: number | null;
  venue: string | null;
  url: string | null;
  doi: string | null;
  abstract: string | null;
  verification_status: string;
  needs_user_correction: boolean;
  authors: string[];
  identifiers: Array<{ type: string; value: string }>;
  source_file_id: string | null;
}

export interface EvidenceLinkPublic {
  id: string;
  chunk_id: string;
  section_id: string | null;
  relation: string;
  note: string | null;
  pinned: boolean;
  exclude_from_ai: boolean;
  passage?: {
    text: string;
    evidence_key: string | null;
    page: number | null;
    source_file_id: string | null;
  };
}

export interface ClaimProvenancePublic {
  id: string;
  claim_text: string;
  evidence_chunk_ids: string[];
  support_score: number | null;
  support_status: string;
  user_verification_status: string;
  citation_required: boolean;
  section_id: string | null;
  generated_at: string;
  model_metadata: Record<string, unknown> | null;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
    request_id?: string | null;
  };
}

/** Advisory overlap / citation-risk — never a plagiarism guarantee. */
export const SIMILARITY_SAFE_SUMMARY =
  'No significant textual overlap was identified within the sources checked.';

export const SIMILARITY_FINDING_CLASSES = [
  'exact_textual_overlap',
  'near_textual_overlap',
  'semantic_similarity',
  'proper_quotation',
  'properly_cited_paraphrase',
  'citation_potentially_required',
  'excessive_similarity_despite_citation',
  'common_technical_phrase',
  'bibliography_or_title_match',
  'self_overlap',
  'internal_duplication',
  'needs_human_review',
] as const;

export type SimilarityFindingClass = (typeof SIMILARITY_FINDING_CLASSES)[number];

export interface SimilarityFindingPublic {
  id: string;
  classification: SimilarityFindingClass | string;
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

export interface SimilarityReportPublic {
  id: string;
  summary_text: string;
  risk_level: string;
  section_summaries: Array<{
    section_id: string;
    title: string;
    finding_count: number;
    risk_level: string;
  }>;
  findings: SimilarityFindingPublic[];
  coverage?: {
    sources_checked: Array<{ label: string; kind: string }>;
    sources_not_checked: Array<{ label?: string; reason?: string }>;
    limitations: string[];
    licensed_provider_status: string;
  };
  footer: Record<string, unknown>;
  method_explanations: Record<string, string>;
}

export const EXPORT_TEMPLATE_IDS = [
  'generic_academic',
  'ieee_two_column',
  'springer_lncs',
  'acm',
] as const;

export type ExportTemplateId = (typeof EXPORT_TEMPLATE_IDS)[number];

export const EXPORT_ARTIFACT_KINDS = [
  'docx',
  'latex',
  'pdf',
  'overleaf_zip',
  'bibtex',
  'figures_zip',
  'dataset_manifest_zip',
  'similarity_report_pdf',
  'submission_package',
  'html_preview',
  'provenance_manifest',
  'canonical_json',
] as const;

export type ExportArtifactKind = (typeof EXPORT_ARTIFACT_KINDS)[number];

export const EXPORT_TEMPLATE_WARNING =
  'These are compatible starting templates, not officially certified publisher formats. Authors must verify current journal or conference submission requirements before use.';

export const GATED_ACTIONS = [
  'save',
  'upload',
  'full_export',
  'full_similarity_check',
  'generate_full_section',
] as const;

export type GatedAction = (typeof GATED_ACTIONS)[number];

export const GUEST_STORAGE_KEY = 'researchforge.guestDraft.v1';
export const GUEST_PENDING_SAVE_KEY = 'researchforge.guestPendingSave.v1';

export const GUEST_STORAGE_MESSAGE =
  'Your draft stays in this browser until you sign in. Outline generation may send research metadata to the AI provider and is not saved as a server project. Sign in to save permanently and continue from another device.';
