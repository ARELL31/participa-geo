"""DTOs for the ``/territories`` read endpoint."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class TerritoryDTO(BaseModel):
    """A reference municipality with its comparability statuses."""

    id: UUID
    name: str
    state_code: str
    municipality_code: str
    identity_status: str | None = None
    footprint_status: str | None = None
    reference_date: date | None = None


__all__ = ["TerritoryDTO"]
