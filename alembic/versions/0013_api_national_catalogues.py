"""Expose code-only national catalogues to the read-only API role.

Revision ID: 0013
Revises: 0012
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE VIEW api_district_catalogue AS "
        "SELECT state_code,district_code,label,district_plan FROM geo_district_2023"
    )
    op.execute("GRANT SELECT ON api_district_catalogue TO api")
    op.execute("CREATE VIEW api_state_catalogue AS SELECT state_code,name FROM geo_state")
    op.execute("GRANT SELECT ON api_state_catalogue TO api")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS api_state_catalogue")
    op.execute("DROP VIEW IF EXISTS api_district_catalogue")
