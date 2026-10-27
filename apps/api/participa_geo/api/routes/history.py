"""``GET /participation/history`` — municipal history or summed state aggregates."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from participa_geo.api.deps import SessionDep
from participa_geo.api.metadata import build_meta
from participa_geo.api.schemas.common import Page
from participa_geo.api.schemas.history import ElectionYear, HistoryDTO
from participa_geo.db.repository import Repository

router = APIRouter()

GEOGRAPHIC_WARNING = (
    "Referencia cartográfica: diciembre de 2025 (INE 15DIC2025). Los agregados "
    "estatales suman conteos antes de recalcular tasas (nunca promedian tasas)."
)


@router.get(
    "/participation/history", response_model=Page[HistoryDTO], tags=["participation"]
)
def list_history(
    territory_id: UUID | None = None,
    year: ElectionYear | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=125)] = 25,
    *,
    session: SessionDep,
) -> Page[HistoryDTO]:
    repo = Repository(session)
    records, total = repo.get_history(
        territory_id=territory_id, year=year, page=page, page_size=page_size
    )
    items = [
        HistoryDTO(
            territory_id=r.territory_id,
            year=r.year,
            name=r.name,
            municipality_code=r.municipality_code,
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
            "year": year,
            "page": page,
            "page_size": page_size,
        },
    )
    return Page(items=items, page=page, page_size=page_size, total=total, meta=meta)
