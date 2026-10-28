"""Add level- and district-plan-aware territorial identity columns.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS supports both an upgraded MVP schema and a clean install where
    # 0001 materialized the current SQLAlchemy metadata.
    op.execute(
        "ALTER TABLE territory_version ADD COLUMN IF NOT EXISTS level "
        "varchar(32) NOT NULL DEFAULT 'municipality'"
    )
    op.execute(
        "ALTER TABLE territory_version ADD COLUMN IF NOT EXISTS territory_code varchar(3)"
    )
    op.execute(
        "ALTER TABLE territory_version ADD COLUMN IF NOT EXISTS district_plan varchar(16)"
    )
    op.execute("ALTER TABLE territory_version ADD COLUMN IF NOT EXISTS valid_from date")
    op.execute("ALTER TABLE territory_version ADD COLUMN IF NOT EXISTS valid_to date")
    op.execute("ALTER TABLE territory_version ALTER COLUMN municipality_code DROP NOT NULL")
    op.execute(
        "UPDATE territory_version SET territory_code = municipality_code "
        "WHERE territory_code IS NULL AND level = 'municipality'"
    )
    op.execute(
        "ALTER TABLE territory_version ALTER COLUMN territory_code SET NOT NULL"
    )

    for table in ("observation", "model_run", "prediction", "scenario", "scenario_result"):
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS level "
            "varchar(32) NOT NULL DEFAULT 'municipality'"
        )
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS district_plan varchar(16)"
        )

    # Legacy Jalisco rows have always represented municipalities. They stay on
    # the old municipal reference frame; district plans are not assigned to them.
    op.execute(
        "UPDATE territory_version SET level = 'municipality', district_plan = NULL "
        "WHERE district_plan IS NULL AND municipality_code IS NOT NULL"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_territory_version_national_key "
        "ON territory_version (level, state_code, territory_code, district_plan)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_observation_level_plan_year "
        "ON observation (level, district_plan, year)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_model_run_level_plan "
        "ON model_run (level, district_plan)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_prediction_level_plan "
        "ON prediction (level, district_plan)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_scenario_level_plan "
        "ON scenario (level, district_plan)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_scenario_result_level_plan "
        "ON scenario_result (level, district_plan)"
    )

    for table, constraint in (
        ("territory_version", "ck_territory_version_national_identity"),
        ("observation", "ck_observation_national_level_plan"),
        ("model_run", "ck_model_run_national_level_plan"),
        ("prediction", "ck_prediction_national_level_plan"),
        ("scenario", "ck_scenario_national_level_plan"),
        ("scenario_result", "ck_scenario_result_national_level_plan"),
    ):
        if table == "territory_version":
            expression = (
                "(level = 'municipality' AND district_plan IS NULL "
                "AND municipality_code IS NOT NULL) OR "
                "(level = 'federal_district' AND district_plan IN ('DERFE2021', 'DERFE2023') "
                "AND municipality_code IS NULL)"
            )
        else:
            expression = (
                "(level = 'municipality' AND district_plan IS NULL) OR "
                "(level = 'federal_district' AND district_plan IN ('DERFE2021', 'DERFE2023'))"
            )
        op.execute(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint "
            f"WHERE conname = '{constraint}' AND conrelid = '{table}'::regclass) THEN "
            f"ALTER TABLE {table} ADD CONSTRAINT {constraint} CHECK ({expression}); "
            "END IF; END $$;"
        )
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conname = 'ck_territory_version_validity' "
        "AND conrelid = 'territory_version'::regclass) THEN "
        "ALTER TABLE territory_version ADD CONSTRAINT ck_territory_version_validity "
        "CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from); "
        "END IF; END $$;"
    )


def downgrade() -> None:
    for table, constraint in (
        ("territory_version", "ck_territory_version_national_identity"),
        ("observation", "ck_observation_national_level_plan"),
        ("model_run", "ck_model_run_national_level_plan"),
        ("prediction", "ck_prediction_national_level_plan"),
        ("scenario", "ck_scenario_national_level_plan"),
        ("scenario_result", "ck_scenario_result_national_level_plan"),
    ):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}")
    op.execute(
        "ALTER TABLE territory_version DROP CONSTRAINT IF EXISTS "
        "ck_territory_version_validity"
    )
    op.execute("DROP INDEX IF EXISTS ix_model_run_level_plan")
    op.execute("DROP INDEX IF EXISTS ix_scenario_result_level_plan")
    op.execute("DROP INDEX IF EXISTS ix_scenario_level_plan")
    op.execute("DROP INDEX IF EXISTS ix_prediction_level_plan")
    op.execute("DROP INDEX IF EXISTS ix_observation_level_plan_year")
    op.execute("DROP INDEX IF EXISTS ix_territory_version_national_key")
    for table in ("observation", "model_run", "prediction", "scenario", "scenario_result"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS district_plan")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS level")
    op.execute("ALTER TABLE territory_version ALTER COLUMN municipality_code SET NOT NULL")
    for column in ("valid_to", "valid_from", "district_plan", "territory_code", "level"):
        op.execute(f"ALTER TABLE territory_version DROP COLUMN IF EXISTS {column}")
