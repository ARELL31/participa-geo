"""Add validated section continuity, DERFE2023 bridges and aggregates.

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS also supports the historical 0001 migration's metadata-wide
    # create_all on a clean install; existing 0005 databases get the DDL here.
    op.execute(
        "CREATE TABLE IF NOT EXISTS section_continuity ("
        "source_year integer NOT NULL CHECK (source_year IN (2009,2012,2015,2018,2021,2024)), "
        "state_code varchar(2) NOT NULL, source_section varchar(8) NOT NULL, "
        "target_section varchar(8), target_district varchar(2), "
        "status varchar(16) NOT NULL CHECK (status IN ('matched','unmatched')), "
        "evidence text NOT NULL, source_catalog_sha256 varchar(64) NOT NULL, "
        "PRIMARY KEY (source_year,state_code,source_section), "
        "CHECK ((status='matched' AND target_section IS NOT NULL AND target_district IS NOT NULL) "
        "OR (status='unmatched' AND target_section IS NULL AND target_district IS NULL)))"
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS bridge_section_district ("
        "state_code varchar(2) NOT NULL, section varchar(8) NOT NULL, "
        "district_plan varchar(16) NOT NULL DEFAULT 'DERFE2023' CHECK (district_plan='DERFE2023'), "
        "municipality_code varchar(3) NOT NULL, district_code varchar(2) NOT NULL, "
        "district_label text NOT NULL, provenance text NOT NULL, "
        "PRIMARY KEY (state_code,section,district_plan))"
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS bridge_municipality_district ("
        "state_code varchar(2) NOT NULL, municipality_code varchar(3) NOT NULL, "
        "district_code varchar(2) NOT NULL, "
        "district_plan varchar(16) NOT NULL DEFAULT 'DERFE2023' CHECK (district_plan='DERFE2023'), "
        "section_count integer NOT NULL CHECK (section_count > 0), is_split boolean NOT NULL, "
        "PRIMARY KEY (state_code,municipality_code,district_code,district_plan))"
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS district_reconstruction_coverage ("
        "year integer NOT NULL CHECK (year IN (2009,2012,2015,2018,2021,2024)), "
        "state_code varchar(2) NOT NULL, district_code varchar(2) NOT NULL, "
        "matched_ln integer NOT NULL CHECK (matched_ln >= 0), "
        "reference_ln integer NOT NULL CHECK (reference_ln >= matched_ln), "
        "coverage double precision NOT NULL CHECK (coverage >= 0 AND coverage <= 1), "
        "status varchar(16) NOT NULL CHECK (status IN ('eligible','insufficient')), "
        "district_plan varchar(16) NOT NULL DEFAULT 'DERFE2023' CHECK (district_plan='DERFE2023'), "
        "PRIMARY KEY (year,state_code,district_code))"
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS agg_municipality_district_year ("
        "year integer NOT NULL CHECK (year IN (2009,2012,2015,2018,2021,2024)), "
        "state_code varchar(2) NOT NULL, municipality_code varchar(3) NOT NULL, "
        "district_code varchar(2) NOT NULL, "
        "district_plan varchar(16) NOT NULL DEFAULT 'DERFE2023' CHECK (district_plan='DERFE2023'), "
        "section_count integer NOT NULL CHECK (section_count > 0), "
        "ln integer NOT NULL, sv integer NOT NULL, nv integer NOT NULL, ns integer NOT NULL, "
        "coverage_status varchar(16) NOT NULL "
        "CHECK (coverage_status IN ('eligible','insufficient')), "
        "CHECK (ln >= 0 AND sv >= 0 AND nv >= 0 AND ns >= 0 AND ln=sv+nv+ns), "
        "PRIMARY KEY (year,state_code,municipality_code,district_code,district_plan))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_section_continuity_target "
        "ON section_continuity (source_year,state_code,target_section)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bridge_section_municipality "
        "ON bridge_section_district (state_code,municipality_code,district_code)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agg_municipality_district_year "
        "ON agg_municipality_district_year (year,state_code,district_code)"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON section_continuity, bridge_section_district, "
        "bridge_municipality_district, district_reconstruction_coverage, "
        "agg_municipality_district_year TO writer"
    )
    op.execute(
        "GRANT SELECT ON bridge_municipality_district, district_reconstruction_coverage, "
        "agg_municipality_district_year TO api"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE SELECT ON bridge_municipality_district, district_reconstruction_coverage, "
        "agg_municipality_district_year FROM api"
    )
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON section_continuity, bridge_section_district, "
        "bridge_municipality_district, district_reconstruction_coverage, "
        "agg_municipality_district_year FROM writer"
    )
    op.execute("DROP TABLE IF EXISTS agg_municipality_district_year")
    op.execute("DROP TABLE IF EXISTS district_reconstruction_coverage")
    op.execute("DROP TABLE IF EXISTS bridge_municipality_district")
    op.execute("DROP TABLE IF EXISTS bridge_section_district")
    op.execute("DROP TABLE IF EXISTS section_continuity")
