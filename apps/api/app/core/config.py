"""Centralized application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AliasChoices, BeforeValidator, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _split_csv(value: object) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise TypeError(f"Expected CSV string or list, got {type(value)!r}")


CsvList = Annotated[list[str], NoDecode, BeforeValidator(_split_csv)]


class Settings(BaseSettings):
    """Runtime configuration for the ResearchForge API."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "ResearchForge"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_v1_prefix: str = "/api/v1"

    secret_key: str = Field(default="dev-only-change-me", min_length=8)
    csrf_secret: str = Field(default="dev-only-csrf-change-me", min_length=8)
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    remember_me_refresh_token_expire_days: int = 30
    session_last_seen_min_interval_seconds: int = 300
    email_verification_expire_hours: int = 48
    password_reset_expire_hours: int = 1
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None
    cookie_access_name: str = "rf_access"
    cookie_refresh_name: str = "rf_refresh"
    cookie_csrf_name: str = "rf_csrf"
    public_app_url: str = "http://localhost:3000"
    email_provider: Literal["console", "fake"] = "console"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/auth/oauth/google/callback"
    google_oauth_enabled: bool = False

    cors_origins: CsvList = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    database_url: str = (
        "postgresql+asyncpg://researchforge:researchforge@localhost:5432/researchforge"
    )
    database_url_sync: str = (
        "postgresql+psycopg://researchforge:researchforge@localhost:5432/researchforge"
    )

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "researchforge"
    s3_region: str = "us-east-1"
    s3_use_ssl: bool = False

    max_upload_bytes: int = 26_214_400
    max_dataset_bytes: int = 26_214_400
    dataset_preview_rows: int = 50
    allowed_upload_content_types: CsvList = Field(
        default_factory=lambda: [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/plain",
            "text/markdown",
            "text/csv",
            "text/x-bibtex",
            "application/x-bibtex",
            "application/x-research-info-systems",
            "application/json",
            "image/png",
            "image/jpeg",
        ]
    )
    upload_signed_url_expire_seconds: int = 900
    embedding_dimensions: int = 64
    chunk_max_chars: int = 1200
    chunk_overlap_chars: int = 120
    malware_scanner: Literal["fake", "none"] = "fake"
    similarity_licensed_provider: Literal["null"] = "null"
    similarity_default_profile: str = "default"
    export_download_expire_seconds: int = 900
    export_max_jobs_per_day: int = 50

    rate_limit_enabled: bool = True
    rate_limit_default: str = "100/minute"

    ai_provider: Literal["openai_compatible", "fake", "vllm"] = Field(
        default="openai_compatible",
        validation_alias=AliasChoices("AI_PROVIDER", "ai_provider", "LLM_PROVIDER"),
    )
    llm_base_url: str = Field(
        default="http://localhost:8001/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "AI_BASE_URL", "ai_base_url"),
    )
    llm_api_key: str = Field(
        default="not-needed-for-local-vllm",
        validation_alias=AliasChoices("LLM_API_KEY", "AI_API_KEY", "ai_api_key"),
    )
    llm_model: str = Field(
        default="researchforge-local",
        validation_alias=AliasChoices("LLM_MODEL", "AI_MODEL_NAME", "ai_model_name"),
    )
    llm_timeout_seconds: int = Field(
        default=120,
        validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS", "AI_TIMEOUT_SECONDS"),
    )
    llm_max_concurrency: int = Field(default=4, validation_alias="LLM_MAX_CONCURRENCY")
    llm_max_output_tokens: int = Field(
        default=2048,
        validation_alias=AliasChoices("LLM_MAX_OUTPUT_TOKENS", "AI_MAX_TOKENS"),
    )
    llm_max_retries: int = 2
    llm_circuit_failure_threshold: int = 5
    llm_circuit_reset_seconds: int = 60
    embedding_base_url: str | None = Field(default=None, validation_alias="EMBEDDING_BASE_URL")
    embedding_model: str = Field(default="researchforge-embed", validation_alias="EMBEDDING_MODEL")
    reranker_base_url: str | None = Field(default=None, validation_alias="RERANKER_BASE_URL")
    reranker_model: str = Field(default="researchforge-rerank", validation_alias="RERANKER_MODEL")
    ai_log_prompt_text: bool = False
    ai_repair_attempts: int = 1
    ai_user_daily_job_limit: int = 50
    ai_project_hourly_job_limit: int = 30
    # Legacy aliases used by older modules/tests
    ai_provider_for_tests: Literal["fake"] = "fake"

    guest_outline_max_sections: int = 6
    training_opt_in_default: bool = False
    trash_retention_days: int = 30
    free_inactive_draft_days: int = 90
    paid_inactive_draft_days: int | None = None
    autosave_snapshot_min_words_delta: int = 40
    deletion_notice_days: int = 7

    @property
    def ai_base_url(self) -> str:
        return self.llm_base_url

    @property
    def ai_api_key(self) -> str:
        return self.llm_api_key

    @property
    def ai_model_name(self) -> str:
        return self.llm_model

    @property
    def ai_timeout_seconds(self) -> int:
        return self.llm_timeout_seconds

    @property
    def ai_max_tokens(self) -> int:
        return self.llm_max_output_tokens

    @field_validator("cookie_domain", mode="before")
    @classmethod
    def empty_domain_to_none(cls, value: object) -> object:
        if value == "" or value == "localhost":
            return None
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def effective_cookie_secure(self) -> bool:
        if self.is_production:
            return True
        return self.cookie_secure

    @property
    def google_oauth_is_configured(self) -> bool:
        return bool(
            self.google_oauth_enabled
            and self.google_oauth_client_id
            and self.google_oauth_client_secret
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
