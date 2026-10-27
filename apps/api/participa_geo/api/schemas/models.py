"""DTOs for the ``/models`` and ``/predictions`` read endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PredictionQuality(BaseModel):
    """The quality decision attached to one prediction (never a numeric zero)."""

    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    identity_status: str | None = None
    footprint_status: str | None = None


class PredictionDTO(BaseModel):
    """One municipality forecast (or ``insufficient`` status) for 2027."""

    territory_id: UUID
    municipality_code: str
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


__all__ = ["ModelDTO", "PredictionDTO", "PredictionQuality"]
