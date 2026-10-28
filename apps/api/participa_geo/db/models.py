"""SQLAlchemy models and record types for the PARTICIPA-GEO persistence layer.

The nine Spec §10 tables are declared here with their ``CHECK`` constraints,
uniqueness and foreign keys. The ``territory_version.geometry`` column is a real
PostGIS ``geometry(Geometry, 4326)``; no ``.set_crs``-style labelling is ever
used (the EPSG:32613 → 4326 transform happens in
``pipelines/validation/geography`` before a geometry reaches this layer).

``TerritoryRecord`` and ``HistoryRecord`` are plain dataclasses (no FastAPI
dependency) that mirror the DTO fields of ``/territories`` and
``/participation/history`` respectively.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from participa_geo.territory import DistrictPlan, TerritoryLevel

#: The six CCPC election years accepted as a historical filter.
ElectionYear = Literal[2009, 2012, 2015, 2018, 2021, 2024]

#: Identity/footprint status values (mirror ``ingestion.schema`` enums).
IDENTITY_STATUSES = ("verified_catalogue", "ambiguous", "known_changed")
FOOTPRINT_STATUSES = ("verified_equal", "not_verified", "known_changed")


class Geometry(UserDefinedType):
    """A PostGIS ``geometry`` column type (no ``geoalchemy2`` dependency).

    ``get_col_spec`` renders ``geometry(GEOMETRY, 4326)`` so Alembic can create
    the column. The type does not translate WKB here: writes use raw SQL with
    ``ST_GeomFromWKB``/``ST_SetSRID`` in the geography import, keeping the CRS
    handling explicit and auditable.
    """

    cache_ok = True

    def __init__(self, geometry_type: str = "GEOMETRY", srid: int = 4326) -> None:
        super().__init__()
        self.geometry_type = geometry_type
        self.srid = srid

    def get_col_spec(self, **kw: object) -> str:
        return f"geometry({self.geometry_type},{self.srid})"


class Base(DeclarativeBase):
    pass


class DatasetVersion(Base):
    __tablename__ = "dataset_version"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False, default="14")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    member: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    encoding: Mapped[str] = mapped_column(String(32), nullable=False, default="utf-8-sig")
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    license_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    dictionary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    __table_args__ = (
        UniqueConstraint("year", "sha256", name="uq_dataset_version_year_sha256"),
        CheckConstraint("year >= 2000", name="ck_dataset_version_year"),
    )


class SectionContinuity(Base):
    __tablename__ = "section_continuity"

    source_year: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    source_section: Mapped[str] = mapped_column(String(8), primary_key=True)
    target_section: Mapped[str | None] = mapped_column(String(8), nullable=True)
    target_district: Mapped[str | None] = mapped_column(String(2), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    source_catalog_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "source_year IN (2009,2012,2015,2018,2021,2024)", name="ck_section_continuity_year"
        ),
        CheckConstraint("status IN ('matched','unmatched')", name="ck_section_continuity_status"),
        CheckConstraint(
            "(status='matched' AND target_section IS NOT NULL AND target_district IS NOT NULL) "
            "OR (status='unmatched' AND target_section IS NULL AND target_district IS NULL)",
            name="ck_section_continuity_target",
        ),
        Index("ix_section_continuity_target", "source_year", "state_code", "target_section"),
    )


class BridgeSectionDistrict(Base):
    __tablename__ = "bridge_section_district"

    state_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    section: Mapped[str] = mapped_column(String(8), primary_key=True)
    district_plan: Mapped[str] = mapped_column(String(16), primary_key=True, default="DERFE2023")
    municipality_code: Mapped[str] = mapped_column(String(3), nullable=False)
    district_code: Mapped[str] = mapped_column(String(2), nullable=False)
    district_label: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("district_plan = 'DERFE2023'", name="ck_bridge_section_district_plan"),
        Index(
            "ix_bridge_section_district_municipality",
            "state_code",
            "municipality_code",
            "district_code",
        ),
    )


class BridgeMunicipalityDistrict(Base):
    __tablename__ = "bridge_municipality_district"

    state_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    municipality_code: Mapped[str] = mapped_column(String(3), primary_key=True)
    district_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    district_plan: Mapped[str] = mapped_column(String(16), primary_key=True, default="DERFE2023")
    section_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_split: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        CheckConstraint("district_plan = 'DERFE2023'", name="ck_bridge_municipality_district_plan"),
        CheckConstraint("section_count > 0", name="ck_bridge_municipality_district_sections"),
    )


class DistrictReconstructionCoverage(Base):
    __tablename__ = "district_reconstruction_coverage"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    district_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    matched_ln: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_ln: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reference_section_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_section_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unmatched_ccpc_section_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unmatched_ccpc_ln: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ccpc_without_mgs_section_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ccpc_without_mgs_ln: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mgs_only_section_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mgs_only_ln: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    section_universe_gap_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    district_plan: Mapped[str] = mapped_column(String(16), nullable=False, default="DERFE2023")

    __table_args__ = (
        CheckConstraint(
            "year IN (2009,2012,2015,2018,2021,2024)", name="ck_district_coverage_year"
        ),
        CheckConstraint(
            "matched_ln >= 0 AND reference_ln >= matched_ln", name="ck_district_coverage_ln"
        ),
        CheckConstraint("coverage >= 0 AND coverage <= 1", name="ck_district_coverage_share"),
        CheckConstraint(
            "status IN ('eligible','insufficient')", name="ck_district_coverage_status"
        ),
        CheckConstraint("district_plan = 'DERFE2023'", name="ck_district_coverage_plan"),
    )


class MunicipalityDistrictYearAggregate(Base):
    __tablename__ = "agg_municipality_district_year"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    municipality_code: Mapped[str] = mapped_column(String(3), primary_key=True)
    district_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    district_plan: Mapped[str] = mapped_column(String(16), primary_key=True, default="DERFE2023")
    section_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ln: Mapped[int] = mapped_column(Integer, nullable=False)
    sv: Mapped[int] = mapped_column(Integer, nullable=False)
    nv: Mapped[int] = mapped_column(Integer, nullable=False)
    ns: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_status: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "year IN (2009,2012,2015,2018,2021,2024)", name="ck_agg_municipality_district_year"
        ),
        CheckConstraint("district_plan = 'DERFE2023'", name="ck_agg_municipality_district_plan"),
        CheckConstraint("section_count > 0", name="ck_agg_municipality_district_sections"),
        CheckConstraint("ln = sv + nv + ns", name="ck_agg_municipality_district_accounting"),
        CheckConstraint(
            "coverage_status IN ('eligible','insufficient')",
            name="ck_agg_municipality_district_status",
        ),
    )


class TerritoryVersion(Base):
    __tablename__ = "territory_version"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    system: Mapped[str] = mapped_column(String(16), nullable=False, default="ine")
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    level: Mapped[TerritoryLevel] = mapped_column(
        String(32), nullable=False, default="municipality", server_default="municipality"
    )
    territory_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default=lambda context: context.get_current_parameters().get("municipality_code"),
    )
    municipality_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    district_plan: Mapped[DistrictPlan | None] = mapped_column(String(16), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    #: Territorial cut date; only the INE 2025 reference carries ``2025-12-15``.
    reference_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Election year for CCPC origin identities (NULL for the 2025 reference).
    origin_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Geometry in EPSG:4326; NULL for historical origin identities.
    geometry: Mapped[object | None] = mapped_column(Geometry("GEOMETRY", 4326), nullable=True)
    #: Declared source SRID of the imported geometry (EPSG:32613 for the reference).
    source_srid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provenance: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    __table_args__ = (
        CheckConstraint(
            "(level = 'municipality' AND district_plan IS NULL AND municipality_code IS NOT NULL) "
            "OR (level = 'federal_district' AND district_plan IS NOT NULL "
            "AND municipality_code IS NULL)",
            name="ck_territory_version_level_plan",
        ),
        CheckConstraint(
            "level IN ('municipality', 'federal_district')", name="ck_territory_version_level"
        ),
        CheckConstraint(
            "district_plan IS NULL OR district_plan IN ('DERFE2021', 'DERFE2023')",
            name="ck_territory_version_district_plan",
        ),
        CheckConstraint(
            "reference_date IS NOT NULL OR origin_year IS NOT NULL",
            name="ck_territory_version_cut",
        ),
        Index("ix_territory_version_reference_date", "reference_date"),
        Index("ix_territory_version_state_code", "state_code", "municipality_code"),
        Index(
            "ix_territory_version_national_key",
            "level",
            "state_code",
            "territory_code",
            "district_plan",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_territory_version_validity",
        ),
    )


class TerritoryCorrespondence(Base):
    __tablename__ = "territory_correspondence"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    origin_territory_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("territory_version.id", ondelete="CASCADE"), nullable=False
    )
    reference_territory_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("territory_version.id", ondelete="CASCADE"), nullable=True
    )
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    identity_status: Mapped[str] = mapped_column(String(32), nullable=False)
    footprint_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    __table_args__ = (
        UniqueConstraint(
            "origin_territory_id",
            "reference_territory_id",
            name="uq_territory_correspondence_pair",
        ),
        CheckConstraint(
            "identity_status IN ('verified_catalogue', 'ambiguous', 'known_changed')",
            name="ck_territory_correspondence_identity",
        ),
        CheckConstraint(
            "footprint_status IN ('verified_equal', 'not_verified', 'known_changed')",
            name="ck_territory_correspondence_footprint",
        ),
    )


class Observation(Base):
    __tablename__ = "observation"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    origin_territory_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("territory_version.id", ondelete="CASCADE"), nullable=False
    )
    dataset_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("dataset_version.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[TerritoryLevel] = mapped_column(
        String(32), nullable=False, default="municipality", server_default="municipality"
    )
    district_plan: Mapped[DistrictPlan | None] = mapped_column(String(16), nullable=True)
    election_type: Mapped[str] = mapped_column(String(16), nullable=False, default="federal")
    ln: Mapped[int] = mapped_column(Integer, nullable=False)
    sv: Mapped[int] = mapped_column(Integer, nullable=False)
    nv: Mapped[int] = mapped_column(Integer, nullable=False)
    ns: Mapped[int] = mapped_column(Integer, nullable=False)
    young_share: Mapped[float | None] = mapped_column(nullable=True)
    senior_share: Mapped[float | None] = mapped_column(nullable=True)
    rural_share: Mapped[float | None] = mapped_column(nullable=True)
    participation_pct: Mapped[float | None] = mapped_column(nullable=True)
    abstention_pct: Mapped[float | None] = mapped_column(nullable=True)
    unknown_share: Mapped[float | None] = mapped_column(nullable=True)
    ns_lower_pct: Mapped[float | None] = mapped_column(nullable=True)
    ns_upper_pct: Mapped[float | None] = mapped_column(nullable=True)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quality_reasons: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    __table_args__ = (
        CheckConstraint(
            "(level = 'municipality' AND district_plan IS NULL) OR "
            "(level = 'federal_district' AND district_plan IN ('DERFE2021', 'DERFE2023'))",
            name="ck_observation_level_plan",
        ),
        UniqueConstraint(
            "origin_territory_id",
            "year",
            "dataset_version_id",
            name="uq_observation_territory_year_dataset",
        ),
        CheckConstraint(
            "ln >= 0 AND sv >= 0 AND nv >= 0 AND ns >= 0",
            name="ck_observation_counts",
        ),
        CheckConstraint("ln = sv + nv + ns", name="ck_observation_accounting"),
        Index("ix_observation_year", "year"),
        Index("ix_observation_level_plan_year", "level", "district_plan", "year"),
    )


class ModelRun(Base):
    __tablename__ = "model_run"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    family: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[TerritoryLevel] = mapped_column(
        String(32), nullable=False, default="municipality", server_default="municipality"
    )
    district_plan: Mapped[DistrictPlan | None] = mapped_column(String(16), nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    features: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    cut_dates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    hashes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    dependencies: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    exclusions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    __table_args__ = (
        CheckConstraint(
            "(level = 'municipality' AND district_plan IS NULL) OR "
            "(level = 'federal_district' AND district_plan IN ('DERFE2021', 'DERFE2023'))",
            name="ck_model_run_level_plan",
        ),
        Index("ix_model_run_level_plan", "level", "district_plan"),
    )


class Prediction(Base):
    __tablename__ = "prediction"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    model_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("model_run.id", ondelete="CASCADE"), nullable=False
    )
    reference_territory_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("territory_version.id", ondelete="CASCADE"), nullable=False
    )
    target_year: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[TerritoryLevel] = mapped_column(
        String(32), nullable=False, default="municipality", server_default="municipality"
    )
    district_plan: Mapped[DistrictPlan | None] = mapped_column(String(16), nullable=True)
    estimated_abstention_pct: Mapped[float | None] = mapped_column(nullable=True)
    historical_error_lower_pct: Mapped[float | None] = mapped_column(nullable=True)
    historical_error_upper_pct: Mapped[float | None] = mapped_column(nullable=True)
    risk: Mapped[str | None] = mapped_column(String(16), nullable=True)
    risk_unstable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quality: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    __table_args__ = (
        CheckConstraint(
            "(level = 'municipality' AND district_plan IS NULL) OR "
            "(level = 'federal_district' AND district_plan IN ('DERFE2021', 'DERFE2023'))",
            name="ck_prediction_level_plan",
        ),
        UniqueConstraint(
            "model_run_id",
            "reference_territory_id",
            "target_year",
            name="uq_prediction_run_territory_year",
        ),
        CheckConstraint("target_year >= 2000", name="ck_prediction_target_year"),
        Index("ix_prediction_level_plan", "level", "district_plan"),
    )


class Scenario(Base):
    __tablename__ = "scenario"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    model_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("model_run.id", ondelete="CASCADE"), nullable=False
    )
    target_year: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[TerritoryLevel] = mapped_column(
        String(32), nullable=False, default="municipality", server_default="municipality"
    )
    district_plan: Mapped[DistrictPlan | None] = mapped_column(String(16), nullable=True)
    reduction_pp: Mapped[float] = mapped_column(nullable=False)
    assumption_code: Mapped[str] = mapped_column(String(32), nullable=False)
    assumption_version: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="'1.0'"
    )
    rationale_text: Mapped[str] = mapped_column(Text, nullable=False)
    rules_version: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="'scenario-rules-1.0.0'"
    )
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False, server_default="''")
    model_sha256: Mapped[str] = mapped_column(String(64), nullable=False, server_default="''")
    selection: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    __table_args__ = (
        CheckConstraint(
            "(level = 'municipality' AND district_plan IS NULL) OR "
            "(level = 'federal_district' AND district_plan IN ('DERFE2021', 'DERFE2023'))",
            name="ck_scenario_level_plan",
        ),
        CheckConstraint(
            "reduction_pp >= 0 AND reduction_pp <= 10", name="ck_scenario_reduction_range"
        ),
        CheckConstraint(
            "assumption_code IN ('preventive_exploration', 'model_sensitivity')",
            name="ck_scenario_assumption_code",
        ),
        Index("ix_scenario_level_plan", "level", "district_plan"),
    )


class ScenarioResult(Base):
    __tablename__ = "scenario_result"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    scenario_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scenario.id", ondelete="CASCADE"), nullable=False
    )
    reference_territory_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("territory_version.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[TerritoryLevel] = mapped_column(
        String(32), nullable=False, default="municipality", server_default="municipality"
    )
    district_plan: Mapped[DistrictPlan | None] = mapped_column(String(16), nullable=True)
    baseline_abstention_pct: Mapped[float | None] = mapped_column(nullable=True)
    hypothetical_abstention_pct: Mapped[float | None] = mapped_column(nullable=True)
    baseline_error_lower_pct: Mapped[float | None] = mapped_column(nullable=True)
    baseline_error_upper_pct: Mapped[float | None] = mapped_column(nullable=True)
    hypothetical_error_lower_pct: Mapped[float | None] = mapped_column(nullable=True)
    hypothetical_error_upper_pct: Mapped[float | None] = mapped_column(nullable=True)
    requested_reduction_pp: Mapped[float] = mapped_column(nullable=False)
    effective_reduction_pp: Mapped[float] = mapped_column(nullable=False)
    risk_a: Mapped[str | None] = mapped_column(String(16), nullable=True)
    risk_b: Mapped[str | None] = mapped_column(String(16), nullable=True)
    risk_a_unstable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    risk_b_unstable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    __table_args__ = (
        CheckConstraint(
            "(level = 'municipality' AND district_plan IS NULL) OR "
            "(level = 'federal_district' AND district_plan IN ('DERFE2021', 'DERFE2023'))",
            name="ck_scenario_result_level_plan",
        ),
        UniqueConstraint(
            "scenario_id",
            "reference_territory_id",
            name="uq_scenario_result_scenario_territory",
        ),
        Index("ix_scenario_result_level_plan", "level", "district_plan"),
    )


class ReportArtifact(Base):
    __tablename__ = "report_artifact"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    sources: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("model_run.id", ondelete="SET NULL"), nullable=True
    )
    scenario_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("scenario.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


@dataclass(frozen=True)
class TerritoryRecord:
    """A reference municipality (the DTO fields of ``/territories``, no FastAPI)."""

    id: UUID
    name: str
    state_code: str
    municipality_code: str
    identity_status: str | None
    footprint_status: str | None
    reference_date: date | None


@dataclass(frozen=True)
class HistoryRecord:
    """One participation record (the DTO fields of ``/participation/history``)."""

    territory_id: UUID | None
    year: int
    name: str | None
    municipality_code: str | None
    ln: int
    sv: int
    nv: int
    ns: int
    participation_pct: float | None
    abstention_pct: float | None
    unknown_share: float | None
    ns_lower_pct: float | None
    ns_upper_pct: float | None
    eligible: bool
    identity_status: str | None
    footprint_status: str | None


@dataclass(frozen=True)
class ModelRecord:
    """One persisted model run (the DTO fields of ``/models``, no FastAPI)."""

    model_run_id: UUID
    family: str
    parameters: dict | None
    features: list | None
    cut_dates: dict | None
    hashes: dict | None
    dependencies: dict | None
    metrics: dict | None
    exclusions: dict | None
    created_at: datetime | None
    level: TerritoryLevel = "municipality"
    district_plan: DistrictPlan | None = None


@dataclass(frozen=True)
class PredictionRecord:
    """One persisted prediction (the DTO fields of ``/predictions``, no FastAPI)."""

    territory_id: UUID
    municipality_code: str | None
    municipality_name: str
    target_year: int
    estimated_abstention_pct: float | None
    historical_error_lower_pct: float | None
    historical_error_upper_pct: float | None
    risk: str | None
    risk_unstable: bool
    eligible: bool
    quality: dict | None
    model_run_id: UUID
    level: TerritoryLevel = "municipality"
    territory_code: str | None = None
    district_plan: DistrictPlan | None = None
    state_code: str = "14"


@dataclass(frozen=True)
class ScenarioRecord:
    """One persisted scenario header (the DTO fields without its results)."""

    scenario_id: UUID
    model_run_id: UUID
    target_year: int
    requested_reduction_pp: float
    assumption_code: str
    assumption_version: str
    rationale_text: str
    rules_version: str
    input_sha256: str
    model_sha256: str
    selection: list[str]
    created_at: datetime
    level: TerritoryLevel = "municipality"
    district_plan: DistrictPlan | None = None


@dataclass(frozen=True)
class ScenarioResultRecord:
    """One persisted municipality result of a scenario (A/B and translated band)."""

    scenario_id: UUID
    territory_id: UUID
    municipality_code: str | None
    municipality_name: str
    baseline_abstention_pct: float | None
    hypothetical_abstention_pct: float | None
    baseline_error_lower_pct: float | None
    baseline_error_upper_pct: float | None
    hypothetical_error_lower_pct: float | None
    hypothetical_error_upper_pct: float | None
    requested_reduction_pp: float
    effective_reduction_pp: float
    risk_a: str
    risk_b: str
    risk_a_unstable: bool
    risk_b_unstable: bool
    selected: bool
    level: TerritoryLevel = "municipality"
    district_plan: DistrictPlan | None = None


__all__ = [
    "Base",
    "BridgeMunicipalityDistrict",
    "BridgeSectionDistrict",
    "DatasetVersion",
    "DistrictReconstructionCoverage",
    "ElectionYear",
    "Geometry",
    "HistoryRecord",
    "ModelRecord",
    "ModelRun",
    "Observation",
    "MunicipalityDistrictYearAggregate",
    "PredictionRecord",
    "Prediction",
    "ReportArtifact",
    "Scenario",
    "ScenarioRecord",
    "ScenarioResult",
    "ScenarioResultRecord",
    "SectionContinuity",
    "TerritoryCorrespondence",
    "TerritoryRecord",
    "TerritoryVersion",
]
