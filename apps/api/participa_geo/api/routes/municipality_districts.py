"""Aggregate-only municipality×district read route."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path

from participa_geo.api.deps import SessionDep
from participa_geo.api.metadata import build_meta
from participa_geo.api.schemas.common import Page
from participa_geo.api.schemas.municipality_district import MunicipalityDistrictDTO
from participa_geo.db.repository import Repository

router = APIRouter()


@router.get(
    "/territories/{territory_id}/municipal-districts",
    response_model=Page[MunicipalityDistrictDTO],
    tags=["territories"],
)
def list_municipality_district_intersections(
    territory_id: Annotated[UUID, Path()], *, session: SessionDep
) -> Page[MunicipalityDistrictDTO]:
    repo = Repository(session)
    rows, total = repo.get_municipality_district_intersections(territory_id)
    items = [MunicipalityDistrictDTO(**row) for row in rows]
    return Page(
        items=items,
        page=1,
        page_size=max(total, 1),
        total=total,
        meta=build_meta(
            dataset_version_ids=repo.get_dataset_version_ids(),
            geographic_warning=(
                "Agregados 2024 por intersección municipio×distrito; no representan "
                "una jerarquía ni contienen filas de sección. Plan distrital 2023."
            ),
            filters={"territory_id": str(territory_id), "year": 2024, "district_plan": "DERFE2023"},
        ),
    )
