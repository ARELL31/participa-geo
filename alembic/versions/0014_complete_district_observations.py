"""Persist complete observed district totals independently of MGS coverage.

Revision ID: 0014
Revises: 0013
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE agg_district_year ("
        "year integer NOT NULL CHECK (year = 2024), "
        "state_code varchar(2) NOT NULL, district_code varchar(2) NOT NULL, "
        "district_plan varchar(16) NOT NULL CHECK (district_plan='DERFE2023'), "
        "section_count integer NOT NULL CHECK (section_count > 0), "
        "ln integer NOT NULL, sv integer NOT NULL, nv integer NOT NULL, ns integer NOT NULL, "
        "CHECK (ln >= 0 AND sv >= 0 AND nv >= 0 AND ns >= 0 AND ln=sv+nv+ns), "
        "PRIMARY KEY (year,state_code,district_code,district_plan))"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON agg_district_year TO writer")
    op.execute("GRANT SELECT ON agg_district_year TO api")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON agg_district_year FROM api")
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON agg_district_year FROM writer")
    op.execute("DROP TABLE IF EXISTS agg_district_year")
