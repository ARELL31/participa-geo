"""Schemas for persisted scenarios and neutral preventive recommendations (T6).

``ScenarioRequest`` is the exact, closed input contract: five fields, no free
text, no unknown identifiers and no non-finite numbers. ``ScenarioDTO`` carries
the full persisted comparison (one result for each of the 125 municipalities),
while ``ScenarioComparison`` is the pure, pre-persistence domain result.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from participa_geo.territory import DistrictPlan, TerritoryLevel

AssumptionCode = Literal["preventive_exploration", "model_sensitivity"]
RiskLevel = Literal["low", "medium", "high", "insufficient"]

#: Never present the translated band as a causal interval.
TRANSLATED_BAND_LABEL = (
    "rango de error histórico de referencia trasladado condicionalmente; no es un intervalo causal"
)


class ScenarioRequest(BaseModel):
    """The closed scenario input (Spec §9; no user-provided text fields)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    model_run_id: UUID
    target_year: Literal[2027]
    level: TerritoryLevel | None = None
    territory_ids: list[UUID] = Field(min_length=1, max_length=1000)
    reduction_pp: float = Field(ge=0.0, le=10.0, allow_inf_nan=False)
    assumption_code: AssumptionCode

    @field_validator("territory_ids")
    @classmethod
    def _territory_ids_are_unique(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("territory_ids debe contener identificadores únicos")
        return value


class ScenarioResultDTO(BaseModel):
    """One municipality's persisted A/B comparison (null when insufficient)."""

    territory_id: UUID
    municipality_code: str | None
    municipality_name: str
    state_code: str | None = None
    level: TerritoryLevel = "municipality"
    territory_code: str | None = None
    district_plan: DistrictPlan | None = None
    baseline_abstention_pct: float | None = None
    hypothetical_abstention_pct: float | None = None
    baseline_error_lower_pct: float | None = None
    baseline_error_upper_pct: float | None = None
    hypothetical_error_lower_pct: float | None = None
    hypothetical_error_upper_pct: float | None = None
    requested_reduction_pp: float
    effective_reduction_pp: float
    risk_a: RiskLevel
    risk_b: RiskLevel
    risk_a_unstable: bool = False
    risk_b_unstable: bool = False
    selected: bool


class ScenarioComparison(BaseModel):
    """Pure result of ``simulate_scenario`` before it is persisted."""

    model_run_id: UUID
    target_year: int
    requested_reduction_pp: float
    assumption_code: AssumptionCode
    level: TerritoryLevel = "municipality"
    district_plan: DistrictPlan | None = None
    assumption_version: str
    rationale_text: str
    rules_version: str
    input_sha256: str
    error_band_label: str = TRANSLATED_BAND_LABEL
    selected_territory_ids: list[UUID]
    results: list[ScenarioResultDTO]


class ScenarioDTO(ScenarioComparison):
    """The persisted scenario plus the full published municipality comparison."""

    scenario_id: UUID
    model_sha256: str
    created_at: datetime


class Recommendation(BaseModel):
    """One fixed, versioned rule output (never generated from user text)."""

    code: str
    version: str
    priority: Literal["data", "high", "medium", "low", "context"]
    title: str
    action: str
    reasons: list[str] = Field(default_factory=list)


class RecommendationDTO(BaseModel):
    """One territory's recommendations under a published model run."""

    territory_id: UUID
    municipality_code: str
    municipality_name: str
    target_year: int
    risk: RiskLevel
    risk_unstable: bool
    eligible: bool
    model_run_id: UUID
    rules_version: str
    recommendations: list[Recommendation]


__all__ = [
    "TRANSLATED_BAND_LABEL",
    "AssumptionCode",
    "Recommendation",
    "RecommendationDTO",
    "RiskLevel",
    "ScenarioComparison",
    "ScenarioDTO",
    "ScenarioRequest",
    "ScenarioResultDTO",
]
