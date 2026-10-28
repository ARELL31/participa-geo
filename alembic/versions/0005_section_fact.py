"""Add partitioned section-grain national CCPC facts.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


YEARS = (2009, 2012, 2015, 2018, 2021, 2024)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE dataset_version ADD COLUMN IF NOT EXISTS state_code varchar(2) "
        "NOT NULL DEFAULT '14'"
    )
    op.execute(
        "CREATE TABLE fact_ccpc_section ("
        "year integer NOT NULL, state_code varchar(2) NOT NULL, "
        "municipality_code varchar(3) NOT NULL, section varchar(8) NOT NULL, "
        "district_2021 varchar(2), district_2023 varchar(2), sex varchar(1) NOT NULL, "
        "age smallint NOT NULL, section_type varchar(1) NOT NULL, "
        "state_name text NOT NULL, municipality_name text NOT NULL, "
        "ln integer NOT NULL, sv integer NOT NULL, nv integer NOT NULL, ns integer NOT NULL, "
        "dataset_version_id uuid NOT NULL REFERENCES dataset_version(id), "
        "source_row integer NOT NULL, source_hash varchar(64) NOT NULL, "
        "source_state_code varchar(8) NOT NULL, source_municipality_code varchar(8) NOT NULL, "
        "source_district varchar(8), "
        "CONSTRAINT ck_fact_ccpc_year CHECK (year IN (2009,2012,2015,2018,2021,2024)), "
        "CONSTRAINT ck_fact_ccpc_counts CHECK (ln >= 0 AND sv >= 0 AND nv >= 0 AND ns >= 0), "
        "CONSTRAINT ck_fact_ccpc_accounting CHECK (ln = sv + nv + ns), "
        "CONSTRAINT uq_fact_ccpc_section UNIQUE "
        "(year,state_code,municipality_code,section,sex,age)"
        ") PARTITION BY RANGE (year)"
    )
    for year in YEARS:
        op.execute(
            f"CREATE TABLE fact_ccpc_section_{year} PARTITION OF fact_ccpc_section "
            f"FOR VALUES FROM ({year}) TO ({year + 1})"
        )
    op.execute(
        "CREATE INDEX ix_fact_ccpc_state_municipality "
        "ON fact_ccpc_section (year,state_code,municipality_code)"
    )
    op.execute(
        "CREATE INDEX ix_fact_ccpc_district_2021 "
        "ON fact_ccpc_section (year,state_code,district_2021)"
    )
    op.execute(
        "CREATE INDEX ix_fact_ccpc_district_2023 "
        "ON fact_ccpc_section (year,state_code,district_2023)"
    )
    op.execute(
        "CREATE INDEX ix_fact_ccpc_source "
        "ON fact_ccpc_section (dataset_version_id,source_hash)"
    )
    # The maintenance writer replaces this table atomically on a re-run; the API
    # and GeoServer remain read-only and receive no grants on native-grain facts.
    op.execute(
        "GRANT SELECT, INSERT, DELETE, TRUNCATE ON fact_ccpc_section TO writer"
    )
    op.execute("REVOKE SELECT ON fact_ccpc_section FROM api")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT, DELETE, TRUNCATE ON fact_ccpc_section FROM writer")
    op.execute("DROP TABLE IF EXISTS fact_ccpc_section CASCADE")
    op.execute("ALTER TABLE dataset_version DROP COLUMN IF EXISTS state_code")
