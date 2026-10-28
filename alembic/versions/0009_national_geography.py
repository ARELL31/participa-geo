"""Store the four validated national MGS geometry layers.

Revision ID: 0009
Revises: 0008
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, columns, primary_key in (
        (
            "geo_state",
            "state_code varchar(2) NOT NULL, name text NOT NULL",
            "state_code",
        ),
        (
            "geo_municipality",
            "state_code varchar(2) NOT NULL, municipality_code varchar(3) NOT NULL, "
            "name text NOT NULL",
            "state_code, municipality_code",
        ),
        (
            "geo_district_2023",
            "state_code varchar(2) NOT NULL, district_code varchar(2) NOT NULL, "
            "label text NOT NULL, district_plan varchar(16) NOT NULL DEFAULT 'DERFE2023' "
            "CHECK (district_plan='DERFE2023')",
            "state_code, district_code",
        ),
        (
            "geo_section",
            "state_code varchar(2) NOT NULL, municipality_code varchar(3) NOT NULL, "
            "section_code varchar(8) NOT NULL, district_code varchar(2) NOT NULL",
            "state_code, section_code",
        ),
    ):
        op.execute(
            f"CREATE TABLE {table} ({columns}, geom geometry(Geometry,4326) NOT NULL, "
            "source_cut date NOT NULL, source_srid integer NOT NULL, "
            "archive_sha256 varchar(64) NOT NULL, provenance text NOT NULL, "
            f"PRIMARY KEY ({primary_key}))"
        )
        op.execute(f"CREATE INDEX ix_{table}_geom ON {table} USING GIST (geom)")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO writer")
        op.execute(f"GRANT SELECT ON {table} TO gis_reader")
    op.execute("GRANT USAGE ON SCHEMA public TO gis_reader")


def downgrade() -> None:
    for table in ("geo_section", "geo_district_2023", "geo_municipality", "geo_state"):
        op.execute(f"DROP TABLE IF EXISTS {table}")
