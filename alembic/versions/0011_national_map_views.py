"""Create bounded-detail national map views; source geometries stay complete.

Revision ID: 0011
Revises: 0010
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, view, attrs in (
        ("geo_state", "geo_state_national_view", "state_code,name"),
        (
            "geo_municipality",
            "geo_municipality_national_view",
            "state_code,municipality_code,name",
        ),
        (
            "geo_district_2023",
            "geo_district_2023_national_view",
            "state_code,district_code,label,district_plan",
        ),
    ):
        op.execute(
            f"CREATE VIEW {view} AS SELECT id,{attrs}, "
            "ST_SimplifyPreserveTopology(geom, 0.005) AS geom, "
            "source_cut,source_srid,archive_sha256,provenance "
            f"FROM {table}"
        )
        op.execute(f"GRANT SELECT ON {view} TO gis_reader")


def downgrade() -> None:
    for view in (
        "geo_district_2023_national_view",
        "geo_municipality_national_view",
        "geo_state_national_view",
    ):
        op.execute(f"DROP VIEW IF EXISTS {view}")
