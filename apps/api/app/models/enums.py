"""Shared enum types for auth, accounts, and projects."""

from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_DELETION = "pending_deletion"
    DELETED = "deleted"


class SubscriptionPlan(StrEnum):
    FREE = "free"
    RESEARCHER = "researcher"
    LAB = "lab"


class AuditAction(StrEnum):
    REGISTER = "register"
    LOGIN = "login"
    LOGOUT = "logout"
    VERIFY_EMAIL = "verify_email"
    REQUEST_PASSWORD_RESET = "request_password_reset"
    RESET_PASSWORD = "reset_password"
    REFRESH = "refresh"
    REFRESH_REUSE = "refresh_reuse_detected"
    REVOKE_SESSION = "revoke_session"
    REVOKE_OTHER_SESSIONS = "revoke_other_sessions"
    UPDATE_ACCOUNT = "update_account"
    DELETE_ACCOUNT = "delete_account"
    EXPORT_ACCOUNT_DATA = "export_account_data"
    GUEST_DRAFT_CONVERTED = "guest_draft_converted"
    OAUTH_LINK = "oauth_link"
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    PROJECT_TRASHED = "project_trashed"
    PROJECT_RESTORED = "project_restored"
    PROJECT_PURGED = "project_purged"
    MANUSCRIPT_SAVED = "manuscript_saved"
    VERSION_CREATED = "version_created"
    VERSION_RESTORED = "version_restored"


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    TRASH = "trash"


class RetentionPolicy(StrEnum):
    KEEP = "keep"
    TRASH_30 = "trash_30"
    INACTIVE_DRAFT_90 = "inactive_draft_90"
    PLAN_DEFAULT = "plan_default"


class SectionType(StrEnum):
    ABSTRACT = "abstract"
    KEYWORDS = "keywords"
    INTRODUCTION = "introduction"
    RELATED_WORK = "related_work"
    METHODOLOGY = "methodology"
    RESULTS = "results"
    DISCUSSION = "discussion"
    LIMITATIONS = "limitations"
    CONCLUSION = "conclusion"
    REFERENCES = "references"
    CUSTOM = "custom"


class SectionStatus(StrEnum):
    EMPTY = "empty"
    DRAFT = "draft"
    COMPLETE = "complete"


class VersionAuthorType(StrEnum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"


class FactCategory(StrEnum):
    PROBLEM = "problem"
    CONTRIBUTION = "contribution"
    DATASET = "dataset"
    EXPERIMENT = "experiment"
    EVALUATION = "evaluation"
    ETHICS = "ethics"
    OTHER = "other"


class MilestoneType(StrEnum):
    RESEARCH_PLAN_APPROVED = "research_plan_approved"
    FIRST_SECTION_COMPLETED = "first_section_completed"
    DATASET_ADDED = "dataset_added"
    FIRST_ANALYSIS_COMPLETED = "first_analysis_completed"
    ALL_CITATIONS_VERIFIED = "all_citations_verified"
    ALL_FIGURES_RESOLVED = "all_figures_resolved"
    INTEGRITY_REVIEW_COMPLETED = "integrity_review_completed"
    FIRST_FULL_DRAFT_COMPLETED = "first_full_draft_completed"
    SUBMISSION_PACKAGE_GENERATED = "submission_package_generated"


class DailyGoalType(StrEnum):
    COMPLETE_SECTION = "complete_a_section"
    VERIFY_REFERENCES = "verify_references"
    ANALYZE_DATASET = "analyze_a_dataset"
    RESOLVE_SIMILARITY = "resolve_similarity_findings"
    CREATE_FIGURES = "create_figures"
    PREPARE_EXPORT = "prepare_export"


class NotificationKind(StrEnum):
    DRAFT_SCHEDULED_DELETION = "draft_scheduled_for_deletion"
    TRASH_EXPIRATION = "trash_expiration"
    COLLABORATOR_ACTIVITY = "collaborator_activity"
    EXPORT_COMPLETED = "export_completed"
    SIMILARITY_REPORT_COMPLETED = "similarity_report_completed"
    SUBMISSION_DATE_APPROACHING = "submission_date_approaching"
    WEEKLY_PROJECT_SUMMARY = "weekly_project_summary"
    WRITING_REMINDERS = "writing_reminders"


class AnalyticsEventType(StrEnum):
    ACCOUNT_CREATED = "account_created"
    PROJECT_CREATED = "project_created"
    SECTION_COMPLETED = "section_completed"
    EXPORT_REQUESTED = "export_requested"
    DRAFT_CONVERTED_FROM_GUEST = "draft_converted_from_guest"
    SIMILARITY_REPORT_COMPLETED = "similarity_report_completed"
    DATASET_ANALYZED = "dataset_analyzed"


class FactSourceType(StrEnum):
    USER = "user"
    AI = "ai"
    IMPORT = "import"
    SYSTEM = "system"


class FactVerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    DISPUTED = "disputed"


class AIJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIOperation(StrEnum):
    OUTLINE = "outline"
    SECTION_QUESTIONS = "section_questions"
    DRAFT_SECTION = "draft_section"
    REWRITE_CLARITY = "rewrite_clarity"
    SHORTEN = "shorten"
    EXPAND_WITH_EVIDENCE = "expand_with_evidence"
    MISSING_INFORMATION = "missing_information"
    GENERATE_ABSTRACT = "generate_abstract"
    GENERATE_LIMITATIONS = "generate_limitations"
    CONSISTENCY_REVIEW = "consistency_review"


class AIProposalStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    PARTIALLY_ACCEPTED = "partially_accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class FileKind(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"
    BIBTEX = "bibtex"
    RIS = "ris"
    CSV = "csv"
    XLSX = "xlsx"
    PNG = "png"
    JPEG = "jpeg"
    OTHER = "other"


class FileProcessingStatus(StrEnum):
    PENDING = "pending"
    SCANNING = "scanning"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class ReferenceVerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    NEEDS_CORRECTION = "needs_correction"
    DUPLICATE = "duplicate"


class EvidenceRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    BACKGROUND = "background"
    METHOD = "method"


class ClaimSupportStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    CITATION_MISSING = "citation_missing"
    USER_PROVIDED_FACT = "user_provided_fact"
    CALCULATED_RESULT = "calculated_result"


class DatasetProvenanceType(StrEnum):
    UPLOADED_REAL = "uploaded_real"
    PUBLICLY_SOURCED = "publicly_sourced"
    SYNTHETIC = "synthetic"
    SIMULATED_EXPERIMENT = "simulated_experiment"
    CALCULATED_RESULT = "calculated_result"
    USER_ENTERED = "user_entered"


class DatasetColumnType(StrEnum):
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    CATEGORY = "category"
    STRING = "string"
    DATETIME = "datetime"


class AnalysisOperation(StrEnum):
    DESCRIPTIVE = "descriptive"
    CORRELATION = "correlation"
    MISSING_VALUES = "missing_values"
    GROUP_COMPARISON = "group_comparison"
    CONFIDENCE_INTERVALS = "confidence_intervals"
    T_TEST = "t_test"
    MANN_WHITNEY = "mann_whitney"
    ANOVA = "anova"
    CHI_SQUARE = "chi_square"
    SIMPLE_REGRESSION = "simple_regression"
    CLASSIFICATION_METRICS = "classification_metrics"
    CONFUSION_MATRIX = "confusion_matrix"
    ROC_CURVE = "roc_curve"
    PRECISION_RECALL = "precision_recall"


class FigureKind(StrEnum):
    BAR = "bar"
    LINE = "line"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    BOX = "box"
    CORRELATION_HEATMAP = "correlation_heatmap"
    CONFUSION_MATRIX = "confusion_matrix"
    ROC_CURVE = "roc_curve"
    PRECISION_RECALL = "precision_recall"
    CONCEPTUAL = "conceptual"


class TableKind(StrEnum):
    DATASET_SUMMARY = "dataset_summary"
    DESCRIPTIVE_STATS = "descriptive_stats"
    PERFORMANCE_COMPARISON = "performance_comparison"
    HYPERPARAMETERS = "hyperparameters"
    ABLATION = "ablation"
    STATISTICAL_TEST = "statistical_test"


class AnalysisRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SimilarityJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SimilarityFindingClass(StrEnum):
    EXACT_TEXTUAL_OVERLAP = "exact_textual_overlap"
    NEAR_TEXTUAL_OVERLAP = "near_textual_overlap"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    PROPER_QUOTATION = "proper_quotation"
    PROPERLY_CITED_PARAPHRASE = "properly_cited_paraphrase"
    CITATION_POTENTIALLY_REQUIRED = "citation_potentially_required"
    EXCESSIVE_SIMILARITY_DESPITE_CITATION = "excessive_similarity_despite_citation"
    COMMON_TECHNICAL_PHRASE = "common_technical_phrase"
    BIBLIOGRAPHY_OR_TITLE_MATCH = "bibliography_or_title_match"
    SELF_OVERLAP = "self_overlap"
    INTERNAL_DUPLICATION = "internal_duplication"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class FindingResolutionAction(StrEnum):
    UNRESOLVED = "unresolved"
    FALSE_POSITIVE = "false_positive"
    ADDED_CITATION = "added_citation"
    REWRITTEN = "rewritten"
    ACCEPTED_TECHNICAL_LANGUAGE = "accepted_technical_language"
    NEEDS_REVIEW = "needs_review"


class SimilaritySourceKind(StrEnum):
    UPLOADED_REFERENCE = "uploaded_reference"
    PROJECT_DOCUMENT = "project_document"
    AUTHORIZED_PRIOR_MANUSCRIPT = "authorized_prior_manuscript"
    OPEN_LICENSE_CORPUS = "open_license_corpus"
    INTERNAL_SECTION = "internal_section"
    LICENSED_PROVIDER = "licensed_provider"


class ExportJobStatus(StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    RENDERING = "rendering"
    PACKAGING = "packaging"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class ExportArtifactKind(StrEnum):
    DOCX = "docx"
    LATEX = "latex"
    PDF = "pdf"
    OVERLEAF_ZIP = "overleaf_zip"
    BIBTEX = "bibtex"
    FIGURES_ZIP = "figures_zip"
    DATASET_MANIFEST_ZIP = "dataset_manifest_zip"
    SIMILARITY_REPORT_PDF = "similarity_report_pdf"
    SUBMISSION_PACKAGE = "submission_package"
    HTML_PREVIEW = "html_preview"
    PROVENANCE_MANIFEST = "provenance_manifest"
    CANONICAL_JSON = "canonical_json"


class ExportTemplateId(StrEnum):
    GENERIC_ACADEMIC = "generic_academic"
    IEEE_TWO_COLUMN = "ieee_two_column"
    SPRINGER_LNCS = "springer_lncs"
    ACM = "acm"


class ExportValidationSeverity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"
