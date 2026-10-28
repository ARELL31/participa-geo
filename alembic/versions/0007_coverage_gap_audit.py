"""Persist section-universe gap counts alongside coverage gates.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in (
        "reference_section_count",
        "matched_section_count",
        "unmatched_ccpc_section_count",
        "unmatched_ccpc_ln",
        "ccpc_without_mgs_section_count",
        "ccpc_without_mgs_ln",
        "mgs_only_section_count",
        "mgs_only_ln",
    ):
        op.execute(
            f"ALTER TABLE district_reconstruction_coverage "
            f"ADD COLUMN IF NOT EXISTS {column} integer NOT NULL DEFAULT 0"
        )


def downgrade() -> None:
    for column in (
        "mgs_only_ln",
        "mgs_only_section_count",
        "ccpc_without_mgs_ln",
        "ccpc_without_mgs_section_count",
        "unmatched_ccpc_ln",
        "unmatched_ccpc_section_count",
        "matched_section_count",
        "reference_section_count",
    ):
        op.execute(f"ALTER TABLE district_reconstruction_coverage DROP COLUMN IF EXISTS {column}")
