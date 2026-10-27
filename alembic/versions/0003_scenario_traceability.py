"""Persist scenario traceability fields and let the API insert scenarios.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-26

T3 created the ``scenario``/``scenario_result`` tables but the T6 contract needs
the translated historical-error band, both instability flags, the assumption and
rules versions and the input/model hashes. T6 also writes scenarios from the HTTP
process, so the least-privilege ``api`` role receives ``INSERT`` on exactly the
two scenario tables (it remains read-only for every other table and never gets
UPDATE/DELETE).

Existing rows are preserved: new columns are added with defaults where needed.
``IF NOT EXISTS`` makes the revision safe for a database created from the current
model metadata (fresh test databases run 0001 with the model columns already
present, then this revision is a no-op for those columns).
"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE scenario ADD COLUMN IF NOT EXISTS "
        "assumption_version character varying(16) NOT NULL DEFAULT '1.0'"
    )
    op.execute(
        "ALTER TABLE scenario ADD COLUMN IF NOT EXISTS "
        "rules_version character varying(32) NOT NULL "
        "DEFAULT 'scenario-rules-1.0.0'"
    )
    op.execute(
        "ALTER TABLE scenario ADD COLUMN IF NOT EXISTS "
        "input_sha256 character varying(64) NOT NULL DEFAULT ''"
    )
    op.execute(
        "ALTER TABLE scenario ADD COLUMN IF NOT EXISTS "
        "model_sha256 character varying(64) NOT NULL DEFAULT ''"
    )

    op.execute(
        "ALTER TABLE scenario_result ADD COLUMN IF NOT EXISTS "
        "baseline_error_lower_pct double precision"
    )
    op.execute(
        "ALTER TABLE scenario_result ADD COLUMN IF NOT EXISTS "
        "baseline_error_upper_pct double precision"
    )
    op.execute(
        "ALTER TABLE scenario_result ADD COLUMN IF NOT EXISTS "
        "hypothetical_error_lower_pct double precision"
    )
    op.execute(
        "ALTER TABLE scenario_result ADD COLUMN IF NOT EXISTS "
        "hypothetical_error_upper_pct double precision"
    )
    op.execute(
        "ALTER TABLE scenario_result ADD COLUMN IF NOT EXISTS "
        "risk_a_unstable boolean NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE scenario_result ADD COLUMN IF NOT EXISTS "
        "risk_b_unstable boolean NOT NULL DEFAULT false"
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_scenario_assumption_code'
                  AND conrelid = 'scenario'::regclass
            ) THEN
                ALTER TABLE scenario
                ADD CONSTRAINT ck_scenario_assumption_code
                CHECK (assumption_code IN ('preventive_exploration', 'model_sensitivity'));
            END IF;
        END
        $$;
        """
    )

    # Render the B classification for the published map style (the style reads a
    # single ``risk`` attribute). A/B and the translated band remain available.
    op.execute(
        """
        CREATE OR REPLACE VIEW scenario_results AS
        SELECT
            s.id,
            s.scenario_id,
            s.baseline_abstention_pct,
            s.hypothetical_abstention_pct,
            s.requested_reduction_pp,
            s.effective_reduction_pp,
            s.risk_a,
            s.risk_b,
            s.selected,
            t.municipality_code,
            t.name,
            t.geometry,
            s.risk_b AS risk,
            s.baseline_error_lower_pct,
            s.baseline_error_upper_pct,
            s.hypothetical_error_lower_pct,
            s.hypothetical_error_upper_pct,
            s.risk_a_unstable,
            s.risk_b_unstable
        FROM scenario_result s
        JOIN territory_version t ON t.id = s.reference_territory_id
        """
    )

    # The HTTP process creates scenarios; it still cannot update or delete them,
    # nor write any other business table.
    op.execute("GRANT INSERT ON scenario, scenario_result TO api")


def downgrade() -> None:
    op.execute("REVOKE INSERT ON scenario, scenario_result FROM api")
    op.execute("DROP VIEW IF EXISTS scenario_results CASCADE")
    op.execute(
        """
        CREATE VIEW scenario_results AS
        SELECT
            s.id,
            s.scenario_id,
            s.baseline_abstention_pct,
            s.hypothetical_abstention_pct,
            s.requested_reduction_pp,
            s.effective_reduction_pp,
            s.risk_a,
            s.risk_b,
            s.selected,
            t.municipality_code,
            t.name,
            t.geometry
        FROM scenario_result s
        JOIN territory_version t ON t.id = s.reference_territory_id
        """
    )
    op.execute("GRANT SELECT ON scenario_results TO gis_reader")
    op.execute(
        "ALTER TABLE scenario DROP CONSTRAINT IF EXISTS ck_scenario_assumption_code"
    )
    for column in (
        "baseline_error_lower_pct",
        "baseline_error_upper_pct",
        "hypothetical_error_lower_pct",
        "hypothetical_error_upper_pct",
        "risk_a_unstable",
        "risk_b_unstable",
    ):
        op.execute(f"ALTER TABLE scenario_result DROP COLUMN IF EXISTS {column}")
    for column in (
        "assumption_version",
        "rules_version",
        "input_sha256",
        "model_sha256",
    ):
        op.execute(f"ALTER TABLE scenario DROP COLUMN IF EXISTS {column}")
