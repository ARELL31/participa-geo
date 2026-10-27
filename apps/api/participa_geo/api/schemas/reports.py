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

ReportKind = Literal[
    "history_csv",
    "history_xlsx",
    "scenario_csv",
    "scenario_geojson",
    "scenario_pdf",
    "scenario_map_png",
    "scenario_map_pdf",
    "methodology_pdf",
    "executive_pdf",
    "technical_zip",
]
ReportFormat = Literal["csv", "xlsx", "geojson", "pdf", "png", "zip"]
ReportStatus = Literal["ready", "failed"]

HISTORY_KINDS = frozenset({"history_csv", "history_xlsx"})
SCENARIO_KINDS = frozenset(
    {
        "scenario_csv",
        "scenario_geojson",
        "scenario_pdf",
        "scenario_map_png",
        "scenario_map_pdf",
    }
)
INSTITUTIONAL_KINDS = frozenset(
    {"methodology_pdf", "executive_pdf", "technical_zip"}
)

#: Fixed version included in every cache key and metadata block.
REPORT_RULES_VERSION = "report-rules-1.0.0"

FORMAT_BY_KIND: dict[str, ReportFormat] = {
    "history_csv": "csv",
    "history_xlsx": "xlsx",
    "scenario_csv": "csv",
    "scenario_geojson": "geojson",
    "scenario_pdf": "pdf",
    "scenario_map_png": "png",
    "scenario_map_pdf": "pdf",
    "methodology_pdf": "pdf",
    "executive_pdf": "pdf",
    "technical_zip": "zip",
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

    @model_validator(mode="after")
    def _check_kind_arguments(self) -> ReportRequest:
        if self.kind in SCENARIO_KINDS:
            if self.scenario_id is None:
                raise ValueError("scenario_id es obligatorio para exportaciones de escenario")
        elif self.scenario_id is not None:
            raise ValueError("scenario_id sólo aplica a exportaciones de escenario")

        if self.kind in HISTORY_KINDS:
            return self
        if self.territory_id is not None or self.year is not None:
            raise ValueError(
                "territory_id/year sólo aplican a exportaciones históricas"
            )
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
    "REPORT_RULES_VERSION",
    "SCENARIO_KINDS",
    "ReportArtifactDTO",
    "ReportFormat",
    "ReportKind",
    "ReportRequest",
    "ReportStatus",
]
