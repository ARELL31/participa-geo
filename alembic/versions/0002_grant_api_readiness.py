"""Grant the ``api`` role SELECT on ``alembic_version`` for readiness.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26

The read-only readiness check (T5) verifies that migrations are applied by
reading the Alembic version table. The ``api`` role is otherwise SELECT-only on
the business tables (granted in 0001); this adds the same read access to the
migration bookkeeping table without expanding any role's privileges.
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT SELECT ON alembic_version TO api")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON alembic_version FROM api")
