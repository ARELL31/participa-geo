"""Allow explicit unmatched origin-to-catalogue identity records.

Revision ID: 0012
Revises: 0011
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("territory_correspondence", "reference_territory_id", nullable=True)


def downgrade() -> None:
    op.execute(
        "DELETE FROM territory_correspondence WHERE reference_territory_id IS NULL"
    )
    op.alter_column("territory_correspondence", "reference_territory_id", nullable=False)
