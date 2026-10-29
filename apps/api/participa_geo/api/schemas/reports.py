"""Closed request/response schemas for the report API (T9).

``ReportRequest`` is deliberately tiny and closed: a kind, an optional persisted
scenario, a municipality and one of the six election years. There is no URL,
template, path or free-text field, so the API can never be pointed at another
storage location or at user-supplied document content.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from participa_geo.api.schemas.history import ElectionYear
from participa_geo.territory import DistrictPlan, TerritoryLevel

ReportKind = Literal[
    "history_csv",
    "history_xlsx",
    "model_evidence_csv",
    "model_evidence_xlsx",
    "scenario_csv",
    "scenario_geojson",
    "scenario_pdf",
    "scenario_map_png",
    "scenario_map_pdf",
    "methodology_pdf",
    "executive_pdf",
    "technical_zip",
    "district_observed_pdf",
    "territory_fiche_pdf",
    "national_geojson",
]
ReportFormat = Literal["csv", "xlsx", "geojson", "pdf", "png", "zip"]
ReportStatus = Literal["ready", "failed"]

HISTORY_KINDS = frozenset({"history_csv", "history_xlsx"})
MODEL_KINDS = frozenset({"model_evidence_csv", "model_evidence_xlsx"})
SCENARIO_KINDS = frozenset(
    {
        "scenario_csv",
        "scenario_geojson",
        "scenario_pdf",
        "scenario_map_png",
        "scenario_map_pdf",
    }
)
INSTITUTIONAL_KINDS = frozenset({"methodology_pdf", "executive_pdf", "technical_zip"})

#: Fixed version included in every cache key and metadata block.
REPORT_RULES_VERSION = "report-rules-1.2.0"

FORMAT_BY_KIND: dict[str, ReportFormat] = {
    "history_csv": "csv",
    "history_xlsx": "xlsx",
    "model_evidence_csv": "csv",
    "model_evidence_xlsx": "xlsx",
    "scenario_csv": "csv",
    "scenario_geojson": "geojson",
    "scenario_pdf": "pdf",
    "scenario_map_png": "png",
    "scenario_map_pdf": "pdf",
    "methodology_pdf": "pdf",
    "executive_pdf": "pdf",
    "technical_zip": "zip",
    "district_observed_pdf": "pdf",
    "territory_fiche_pdf": "pdf",
    "national_geojson": "geojson",
}

MEDIA_TYPE_BY_FORMAT: dict[str, str] = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "geojson": "application/geo+json",
    "pdf": "application/pdf",
    "png": "image/png",
    "zip": "application/zip",
}


class ReportRequest(BaseModel):
    """One closed export request; extra fields (URLs, paths) are rejected."""

    model_config = ConfigDict(extra="forbid")

    kind: ReportKind
    scenario_id: UUID | None = None
    territory_id: UUID | None = None
    year: ElectionYear | None = None
    level: TerritoryLevel = "municipality"
    district_plan: DistrictPlan | None = None
    state_code: str = "all"

    @model_validator(mode="after")
    def _check_kind_arguments(self) -> ReportRequest:
        if self.kind == "district_observed_pdf":
            if self.level != "federal_district" or self.district_plan is None:
                raise ValueError(
                    "district_observed_pdf requiere level=federal_district y district_plan"
                )
            if self.district_plan != "DERFE2023":
                raise ValueError("los reportes distritales requieren district_plan=DERFE2023")
            if self.year not in (None, 2024):
                raise ValueError("el reporte distrital sólo publica Observado 2024")
            if self.territory_id is None or self.scenario_id is not None:
                raise ValueError("la ficha observada requiere territory_id y no admite escenario")
            return self

        if self.kind == "territory_fiche_pdf":
            if self.level != "municipality" or self.district_plan is not None:
                raise ValueError("las fichas estatales/municipales usan level=municipality")
            if self.scenario_id is not None or self.year not in (None, 2024):
                raise ValueError("la ficha observada no admite escenarios y sólo informa 2024")
            if (
                self.state_code == "all"
                or len(self.state_code) != 2
                or not self.state_code.isdigit()
            ):
                raise ValueError("la ficha requiere un código de entidad de dos dígitos")
            return self

        if self.kind == "national_geojson":
            if (
                self.state_code == "all"
                or len(self.state_code) != 2
                or not self.state_code.isdigit()
            ):
                raise ValueError("GeoJSON requiere una entidad específica de dos dígitos")
            if (
                self.scenario_id is not None
                or self.territory_id is not None
                or self.year is not None
            ):
                raise ValueError("GeoJSON nacional no admite escenarios ni filtros de historia")
            if self.level == "federal_district" and self.district_plan != "DERFE2023":
                raise ValueError("GeoJSON distrital requiere district_plan=DERFE2023")
            if self.level == "municipality" and self.district_plan is not None:
                raise ValueError("district_plan sólo aplica a GeoJSON distrital")
            return self

        if self.kind in SCENARIO_KINDS:
            if self.scenario_id is None:
                raise ValueError("scenario_id es obligatorio para exportaciones de escenario")
            if self.level != "municipality" or self.district_plan is not None:
                raise ValueError("los escenarios sólo están disponibles para municipios")
        elif self.scenario_id is not None:
            raise ValueError("scenario_id sólo aplica a exportaciones de escenario")

        if self.kind in HISTORY_KINDS:
            if self.level == "federal_district":
                if self.district_plan is None:
                    raise ValueError("district_plan es obligatorio para nivel distrital")
                if self.district_plan != "DERFE2023":
                    raise ValueError("los reportes distritales requieren district_plan=DERFE2023")
                if self.year not in (None, 2024):
                    raise ValueError("el reporte distrital sólo publica Observado 2024")
            elif self.district_plan is not None:
                raise ValueError("district_plan sólo aplica a nivel distrital")
            return self
        if self.level == "federal_district":
            raise ValueError("este tipo de reporte no está disponible para distritos")
        if self.district_plan is not None:
            raise ValueError("district_plan sólo aplica a nivel distrital")
        if self.territory_id is not None or self.year is not None:
            raise ValueError("territory_id/year sólo aplican a exportaciones históricas")
        return self


class ReportArtifactDTO(BaseModel):
    """Metadata for one generated artifact; never exposes a local path."""

    report_id: UUID
    kind: ReportKind
    format: ReportFormat
    status: ReportStatus
    size_bytes: int = Field(ge=0)
    sha256: str
    created_at: datetime
    download_url: str
    filename: str = ""
    cached: bool = False
    scenario_id: UUID | None = None
    model_run_id: UUID | None = None
    sources: dict = Field(default_factory=dict)


__all__ = [
    "FORMAT_BY_KIND",
    "HISTORY_KINDS",
    "INSTITUTIONAL_KINDS",
    "MEDIA_TYPE_BY_FORMAT",
    "MODEL_KINDS",
    "REPORT_RULES_VERSION",
    "SCENARIO_KINDS",
    "ReportArtifactDTO",
    "ReportFormat",
    "ReportKind",
    "ReportRequest",
    "ReportStatus",
]
