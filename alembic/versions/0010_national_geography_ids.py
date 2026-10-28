"""Expose national codes as WFS attributes while using surrogate feature IDs.

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, key in (
        ("geo_state", "state_code"),
        ("geo_municipality", "state_code, municipality_code"),
        ("geo_district_2023", "state_code, district_code"),
        ("geo_section", "state_code, section_code"),
    ):
        op.execute(f"ALTER TABLE {table} ADD COLUMN id bigint GENERATED ALWAYS AS IDENTITY")
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {table}_pkey PRIMARY KEY (id)")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {table}_natural_key UNIQUE ({key})")


def downgrade() -> None:
    for table, key in (
        ("geo_state", "state_code"),
        ("geo_municipality", "state_code, municipality_code"),
        ("geo_district_2023", "state_code, district_code"),
        ("geo_section", "state_code, section_code"),
    ):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_natural_key")
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        op.execute(f"ALTER TABLE {table} DROP COLUMN id")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {table}_pkey PRIMARY KEY ({key})")
