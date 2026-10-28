"""``GET /participation/history`` — municipal history or summed state aggregates."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query

from participa_geo.api.deps import SessionDep
from participa_geo.api.metadata import build_meta
from participa_geo.api.schemas.common import Page
from participa_geo.api.schemas.history import ElectionYearQuery, HistoryDTO
from participa_geo.db.repository import Repository

router = APIRouter()

GEOGRAPHIC_WARNING = (
    "Referencia cartográfica: diciembre de 2025 (INE 15DIC2025). Los agregados "
    "estatales suman conteos antes de recalcular tasas (nunca promedian tasas)."
)


@router.get("/participation/history", response_model=Page[HistoryDTO], tags=["participation"])
def list_history(
    level: Literal["municipality", "federal_district"] = "municipality",
    state_code: Annotated[str, Query(pattern=r"^(\d{2}|all)$")] = "14",
    territory_id: UUID | None = None,
    year: ElectionYearQuery = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 25,
    *,
    session: SessionDep,
) -> Page[HistoryDTO]:
    repo = Repository(session)
    records, total = repo.get_history(
        territory_id=territory_id,
        year=year,
        page=page,
        page_size=page_size,
        level=level,
        state_code=state_code,
    )
    items = [
        HistoryDTO(
            territory_id=r.territory_id,
            year=r.year,
            name=r.name,
            municipality_code=r.municipality_code,
            level=level,
            territory_code=getattr(r, "territory_code", None),
            district_plan=getattr(r, "district_plan", None),
            coverage_share=getattr(r, "coverage_share", None),
            ln=r.ln,
            sv=r.sv,
            nv=r.nv,
            ns=r.ns,
            participation_pct=r.participation_pct,
            abstention_pct=r.abstention_pct,
            unknown_share=r.unknown_share,
            ns_lower_pct=r.ns_lower_pct,
            ns_upper_pct=r.ns_upper_pct,
            eligible=r.eligible,
            identity_status=r.identity_status,
            footprint_status=r.footprint_status,
        )
        for r in records
    ]
    meta = build_meta(
        dataset_version_ids=repo.get_dataset_version_ids(),
        geographic_warning=GEOGRAPHIC_WARNING,
        filters={
            "territory_id": str(territory_id) if territory_id else None,
            "level": level,
            "state_code": state_code,
            "year": year,
            "page": page,
            "page_size": page_size,
        },
    )
    return Page(items=items, page=page, page_size=page_size, total=total, meta=meta)
