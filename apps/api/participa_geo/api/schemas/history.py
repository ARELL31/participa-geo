"""DTOs for the ``/participation/history`` read endpoint."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

#: The six CCPC election years accepted as a historical filter.
ElectionYear = Literal[2009, 2012, 2015, 2018, 2021, 2024]


class HistoryDTO(BaseModel):
    """One participation record (municipal or state aggregate).

    State aggregates (``territory_id is None``) sum counts across the 125
    municipalities before recomputing rates; insufficient values are ``null``.
    """

    territory_id: UUID | None = None
    year: int
    name: str | None = None
    municipality_code: str | None = None
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


__all__ = ["ElectionYear", "HistoryDTO"]
