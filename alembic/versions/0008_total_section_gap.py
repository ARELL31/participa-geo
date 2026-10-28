"""Persist the combined CCPC/MGS section-universe gap count.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE district_reconstruction_coverage "
        "ADD COLUMN IF NOT EXISTS section_universe_gap_count integer NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE district_reconstruction_coverage "
        "DROP COLUMN IF EXISTS section_universe_gap_count"
    )
