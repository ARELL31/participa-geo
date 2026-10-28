"""DTOs for the ``/models`` and ``/predictions`` read endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field

from participa_geo.territory import DistrictPlan, TerritoryLevel

#: The fixed forecast horizon (Spec §7): only 2027 is a valid target.
TargetYear = Literal[2027]


def _coerce_target_year(value: object) -> object:
    """Coerce a query-string ``target_year`` (``"2027"``) to ``int``.

    Pydantic 2.14 does not coerce ``str`` → ``int`` for ``Literal[2027]`` on its
    own, so the bare annotation rejects the query string with ``literal_error``.
    This keeps 2027 accepted and 2026 (or anything else) a 422.
    """
    if isinstance(value, str):
        return int(value)
    return value


#: ``target_year`` query parameter: coerces the query string to int, then enforces
#: the single approved 2027 horizon. The OpenAPI schema stays ``const: 2027``.
TargetYearQuery = Annotated[TargetYear, BeforeValidator(_coerce_target_year)]


class PredictionQuality(BaseModel):
    """The quality decision attached to one prediction (never a numeric zero)."""

    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    identity_status: str | None = None
    footprint_status: str | None = None


class PredictionDTO(BaseModel):
    """One municipality forecast (or ``insufficient`` status) for 2027."""

    territory_id: UUID
    municipality_code: str | None = None
    level: TerritoryLevel = "municipality"
    territory_code: str | None = None
    district_plan: DistrictPlan | None = None
    municipality_name: str
    target_year: int
    estimated_abstention_pct: float | None = None
    historical_error_lower_pct: float | None = None
    historical_error_upper_pct: float | None = None
    risk: str | None = None
    risk_unstable: bool = False
    eligible: bool
    quality: PredictionQuality | None = None
    model_run_id: UUID


class ModelDTO(BaseModel):
    """A persisted, already-trained model run (no training endpoint exists)."""

    model_run_id: UUID
    family: str
    level: TerritoryLevel = "municipality"
    district_plan: DistrictPlan | None = None
    target_year: int
    reference_date: str
    features: list[str] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)
    cut_dates: dict | None = None
    hashes: dict | None = None
    metrics: dict | None = None
    exclusions: dict | None = None
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


__all__ = [
    "ModelDTO",
    "PredictionDTO",
    "PredictionQuality",
    "TargetYear",
    "TargetYearQuery",
]
