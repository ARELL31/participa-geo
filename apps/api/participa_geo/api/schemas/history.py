"""DTOs for the ``/participation/history`` read endpoint."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator

from participa_geo.territory import DistrictPlan, TerritoryLevel

#: The six CCPC election years accepted as a historical filter.
ElectionYear = Literal[2009, 2012, 2015, 2018, 2021, 2024]


def _coerce_election_year(value: object) -> object:
    """Coerce a query-string year (``"2024"``) to ``int`` before the Literal check.

    Pydantic 2.14 does not coerce ``str`` → ``int`` for a ``Literal[int, ...]`` on
    its own, so a bare ``year: ElectionYear | None`` rejects the query string
    ``"2024"`` with ``literal_error``. This validator makes the six approved years
    parse from query strings while leaving 2023 (and any non-integer) a 422.
    """
    if isinstance(value, str):
        return int(value)
    return value


#: ``year`` query parameter: coerces the query string to int, then enforces the
#: six approved election years. The OpenAPI schema still exposes the integer enum.
ElectionYearQuery = Annotated[ElectionYear | None, BeforeValidator(_coerce_election_year)]


class HistoryDTO(BaseModel):
    """One participation record (municipal or state aggregate).

    State aggregates (``territory_id is None``) sum counts across the 125
    municipalities before recomputing rates; insufficient values are ``null``.
    """

    territory_id: UUID | None = None
    year: int
    name: str | None = None
    municipality_code: str | None = None
    state_code: str | None = None
    level: TerritoryLevel = "municipality"
    territory_code: str | None = None
    district_plan: DistrictPlan | None = None
    ln: int
    sv: int
    nv: int
    ns: int
    participation_pct: float | None = None
    abstention_pct: float | None = None
    unknown_share: float | None = None
    ns_lower_pct: float | None = None
    ns_upper_pct: float | None = None
    eligible: bool
    identity_status: str | None = None
    footprint_status: str | None = None
    coverage_share: float | None = None


__all__ = ["ElectionYear", "ElectionYearQuery", "HistoryDTO"]
