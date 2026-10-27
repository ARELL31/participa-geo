"""Initial PostGIS schema for PARTICIPA-GEO (Spec §10).

Revision ID: 0001
Revises:
Create Date: 2026-10-26

Creates the nine Spec §10 tables (``dataset_version``, ``territory_version``,
``territory_correspondence``, ``observation``, ``model_run``, ``prediction``,
``scenario``, ``scenario_result``, ``report_artifact``) with their CHECK count
constraints, uniqueness and foreign keys, plus the four read-only GeoServer
views (``municipalities``, ``participation_history``, ``predictions``,
``scenario_results``) and the least-privilege grants.

Table/column definitions and constraints live in
``apps/api/participa_geo/db/models.py`` (single source of truth); this migration
materialises them with ``Base.metadata.create_all`` and then adds the spatial
index, the read-only views and the role grants explicitly.

Grants (roles are created cluster-wide by ``db-init.sh``):

- ``migrator`` owns the tables (it runs this migration).
- ``writer``: SELECT/INSERT/UPDATE/DELETE on every table (loads data).
- ``api``: SELECT only (read-only service role; no INSERT/UPDATE).
- ``gis_reader``: SELECT only on the four published views (no UPDATE).
"""

from __future__ import annotations

from alembic import op

from participa_geo.db.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "dataset_version",
    "territory_version",
    "territory_correspondence",
    "observation",
    "model_run",
    "prediction",
    "scenario",
    "scenario_result",
    "report_artifact",
]

VIEWS = [
    "municipalities",
    "participation_history",
    "predictions",
    "scenario_results",
]

_VIEW_DDL = {
    "municipalities": """
        CREATE VIEW municipalities AS
        SELECT id, state_code, municipality_code, name, reference_date, geometry
        FROM territory_version
        WHERE reference_date = DATE '2025-12-15' AND geometry IS NOT NULL
    """,
    "participation_history": """
        CREATE VIEW participation_history AS
        SELECT
            o.id,
            o.year,
            t_ref.municipality_code,
            t_ref.name,
            o.ln, o.sv, o.nv, o.ns,
            o.participation_pct, o.abstention_pct, o.unknown_share,
            o.ns_lower_pct, o.ns_upper_pct,
            o.eligible,
            t_ref.geometry
        FROM observation o
        JOIN territory_correspondence c ON c.origin_territory_id = o.origin_territory_id
        JOIN territory_version t_ref ON t_ref.id = c.reference_territory_id
    """,
    "predictions": """
        CREATE VIEW predictions AS
        SELECT
            p.id,
            p.target_year,
            p.estimated_abstention_pct,
            p.historical_error_lower_pct,
            p.historical_error_upper_pct,
            p.risk,
            p.risk_unstable,
            p.eligible,
            t.municipality_code,
            t.name,
            t.geometry
        FROM prediction p
        JOIN territory_version t ON t.id = p.reference_territory_id
    """,
    "scenario_results": """
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
    """,
}


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Tables + constraints (defined in db/models.py).
    Base.metadata.create_all(bind=bind)

    # 2. Spatial index on the reference geometry.
    op.execute(
        "CREATE INDEX ix_territory_version_geometry "
        "ON territory_version USING GIST (geometry)"
    )

    # 3. Read-only views published by GeoServer (no predictive logic).
    for name in VIEWS:
        op.execute(_VIEW_DDL[name])

    # 4. Least-privilege grants (PUBLIC already has USAGE on the public schema).
    op.execute(
        "GRANT SELECT ON " + ", ".join(TABLES) + " TO api"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        + ", ".join(TABLES)
        + " TO writer"
    )
    op.execute(
        "GRANT SELECT ON " + ", ".join(VIEWS) + " TO gis_reader"
    )


def downgrade() -> None:
    bind = op.get_bind()
    for name in VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {name} CASCADE")
    Base.metadata.drop_all(bind=bind)
