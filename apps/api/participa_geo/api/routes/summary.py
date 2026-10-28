"""National summary with observed map color computed from summed counts."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter

from participa_geo.api.deps import SessionDep
from participa_geo.api.schemas.history import ElectionYearQuery
from participa_geo.api.schemas.national import StateParticipationSummary
from participa_geo.db.repository import Repository

router = APIRouter()


@router.get(
    "/participation/summary",
    response_model=list[StateParticipationSummary],
    tags=["participation"],
)
def participation_summary(
    level: Literal["municipality", "federal_district"] = "municipality",
    year: ElectionYearQuery = 2024,
    *,
    session: SessionDep,
) -> list[StateParticipationSummary]:
    return Repository(session).get_participation_summary(level=level, year=year)
