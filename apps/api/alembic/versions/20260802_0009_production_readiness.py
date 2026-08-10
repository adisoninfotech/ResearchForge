"""production readiness: audit action values for account export

Revision ID: 20260802_0009
Revises: 20260802_0008
Create Date: 2026-08-02 25:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

sa_text = sa.text

revision: str = "20260802_0009"
down_revision: Union[str, None] = "20260802_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Values that may be missing from the original audit_action enum
_AUDIT_VALUES = (
    "export_account_data",
    "project_created",
    "project_updated",
    "project_trashed",
    "project_restored",
    "project_purged",
    "manuscript_saved",
    "version_created",
    "version_restored",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for value in _AUDIT_VALUES:
        # Enum labels are fixed constants from this migration, not user input.
        op.execute(sa_text(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{value}'"))  # noqa: S608


def downgrade() -> None:
    # PostgreSQL cannot remove enum values safely; leave as no-op.
    pass
