"""``GET /territories`` — reference municipalities, stably paginated."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from participa_geo.api.deps import SessionDep
from participa_geo.api.metadata import build_meta
from participa_geo.api.schemas.common import Page
from participa_geo.api.schemas.territories import TerritoryDTO
from participa_geo.db.repository import Repository

router = APIRouter()

GEOGRAPHIC_WARNING = (
    "Referencia cartográfica: diciembre de 2025 (INE 15DIC2025). La serie "
    "histórica se reporta por unidad administrativa INE; no es una serie de "
    "superficie constante."
)


@router.get("/territories", response_model=Page[TerritoryDTO], tags=["territories"])
def list_territories(
    state_code: Annotated[str, Query(pattern=r"^\d{2}$")] = "14",
    level: Literal["municipality"] = "municipality",
    q: Annotated[str | None, Query(max_length=80)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=125)] = 25,
    *,
    session: SessionDep,
) -> Page[TerritoryDTO]:
    repo = Repository(session)
    records, total = repo.get_territories(
        state_code=state_code, q=q, page=page, page_size=page_size
    )
    items = [
        TerritoryDTO(
            id=r.id,
            name=r.name,
            state_code=r.state_code,
            municipality_code=r.municipality_code,
            identity_status=r.identity_status,
            footprint_status=r.footprint_status,
            reference_date=r.reference_date,
        )
        for r in records
    ]
    meta = build_meta(
        dataset_version_ids=repo.get_dataset_version_ids(),
        geographic_warning=GEOGRAPHIC_WARNING,
        filters={
            "state_code": state_code,
            "level": level,
            "q": q,
            "page": page,
            "page_size": page_size,
        },
    )
    return Page(items=items, page=page, page_size=page_size, total=total, meta=meta)
