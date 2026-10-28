"""Read-only aggregate rows for municipal/district intersections."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class MunicipalityDistrictDTO(BaseModel):
    state_code: str
    municipality_code: str
    municipality_name: str | None = None
    district_code: str
    district_name: str | None = None
    district_plan: Literal["DERFE2023"]
    is_split: bool
    year: Literal[2024] = 2024
    section_count: int
    section_share: float
    ln: int | None = None
    sv: int | None = None
    nv: int | None = None
    ns: int | None = None
    ln_share: float | None = None
    abstention_pct: float | None = None
    coverage_share: float | None = None
    coverage_status: Literal["eligible", "insufficient"]


__all__ = ["MunicipalityDistrictDTO"]
