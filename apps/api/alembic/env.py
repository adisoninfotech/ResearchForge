"""Alembic environment — async-aware migrations using sync URL for online mode."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.db.base import Base
from app.models import (  # noqa: F401
    AIJob,
    AIProposal,
    AnalysisArtifact,
    AnalysisRun,
    AuditEvent,
    AuthSession,
    ChunkEmbedding,
    CitationMention,
    ClaimProvenance,
    Dataset,
    DatasetColumn,
    DatasetProfile,
    DatasetVersion,
    DocumentChunk,
    DocumentPage,
    EmailVerificationToken,
    AnalyticsEvent,
    DailyGoal,
    EvidenceLink,
    ExportArtifact,
    ExportDownload,
    ExportJob,
    ExtractedDocument,
    Figure,
    InAppNotification,
    NotificationPreference,
    ProgressEvent,
    ProjectMilestone,
    FileProcessingJob,
    Manuscript,
    ManuscriptAssetRef,
    ManuscriptSection,
    ManuscriptVersion,
    OAuthAccount,
    PasswordResetToken,
    Project,
    ProjectFact,
    ProjectFile,
    Reference,
    ReferenceAuthor,
    ReferenceIdentifier,
    ReportCoverage,
    ReproducibilityManifest,
    FindingResolution,
    SimilarityFinding,
    SimilarityJob,
    SimilarityReport,
    SimilaritySource,
    Table,
    User,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
settings = get_settings()
# set_main_option writes through configparser, where "%" starts an interpolation
# token. A percent-encoded password (e.g. "@" as %40, which the URL spec requires)
# would otherwise raise "invalid interpolation syntax". Doubling the percent signs
# is the documented escape; configparser collapses "%%" back to "%" on read, and
# SQLAlchemy then percent-decodes the password as normal.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
