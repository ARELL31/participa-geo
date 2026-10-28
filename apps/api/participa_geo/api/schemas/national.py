"""National state-level participation summary contracts."""

from __future__ import annotations

from pydantic import BaseModel

from participa_geo.territory import TerritoryLevel


class StateParticipationSummary(BaseModel):
    level: TerritoryLevel
    state_code: str
    state_name: str
    year: int
    ln: int
    sv: int
    nv: int
    ns: int
    observed_abstention_pct: float | None
    eligible_count: int
    insufficient_count: int
    high_risk_count: int
    coverage_share: float | None


__all__ = ["StateParticipationSummary"]
