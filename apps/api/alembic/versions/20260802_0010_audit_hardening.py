"""audit hardening: trash prior status + deletion notice dedupe

Revision ID: 20260802_0010
Revises: 20260802_0009
Create Date: 2026-08-02 26:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0010"
down_revision: Union[str, None] = "20260802_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("status_before_trash", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("deletion_notice_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "deletion_notice_sent_at")
    op.drop_column("projects", "status_before_trash")
