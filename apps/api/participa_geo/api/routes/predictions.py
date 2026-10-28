"""``GET /predictions`` — the deployed model's 2027 forecasts (incl. insufficient)."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request

from participa_geo.api.deps import SessionDep
from participa_geo.api.errors import ProblemException, problem
from participa_geo.api.metadata import build_meta
from participa_geo.api.schemas.common import Page
from participa_geo.api.schemas.models import (
    PredictionDTO,
    PredictionQuality,
    TargetYearQuery,
)
from participa_geo.db.models import PredictionRecord
from participa_geo.db.repository import Repository

router = APIRouter()


def to_prediction_dto(record: PredictionRecord) -> PredictionDTO:
    quality = record.quality or {}
    return PredictionDTO(
        territory_id=record.territory_id,
        municipality_code=record.municipality_code,
        level=record.level,
        territory_code=record.territory_code or record.municipality_code,
        district_plan=record.district_plan,
        municipality_name=record.municipality_name,
        target_year=record.target_year,
        estimated_abstention_pct=record.estimated_abstention_pct,
        historical_error_lower_pct=record.historical_error_lower_pct,
        historical_error_upper_pct=record.historical_error_upper_pct,
        risk=record.risk,
        risk_unstable=record.risk_unstable,
        eligible=record.eligible,
        quality=PredictionQuality(
            eligible=bool(quality.get("eligible", record.eligible)),
            reasons=[str(r) for r in quality.get("reasons", [])],
            identity_status=quality.get("identity_status"),
            footprint_status=quality.get("footprint_status"),
        ),
        model_run_id=record.model_run_id,
    )


@router.get("/predictions", response_model=Page[PredictionDTO], tags=["predictions"])
def list_predictions(
    request: Request,
    level: Literal["municipality", "federal_district"] = "municipality",
    state_code: Annotated[str, Query(pattern=r"^(\d{2}|all)$")] = "14",
    model_run_id: UUID | None = None,
    target_year: TargetYearQuery = 2027,
    territory_id: UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 25,
    *,
    session: SessionDep,
) -> Page[PredictionDTO]:
    if level == "federal_district":
        raise ProblemException(
            problem(
                status=409,
                code="district_model_unavailable",
                title="Modelo distrital no disponible",
                detail=("Sólo hay observaciones distritales de 2024; no existe predicción 2027."),
                instance=request.url.path,
            )
        )
    repo = Repository(session)
    if model_run_id is None:
        model_run_id = repo.get_published_model_run_id()
        if model_run_id is None:
            raise ProblemException(
                problem(
                    status=409,
                    code="conflict",
                    title="Estado en conflicto",
                    detail="No se ha cargado ningún modelo.",
                    instance=request.url.path,
                )
            )
    elif repo.get_model(model_run_id) is None:
        raise ProblemException(
            problem(
                status=404,
                code="not_found",
                title="Recurso no encontrado",
                detail="El recurso solicitado no existe.",
                instance=request.url.path,
            )
        )

    records, total = repo.get_predictions(
        model_run_id=model_run_id,
        target_year=target_year,
        territory_id=territory_id,
        page=page,
        page_size=page_size,
        level=level,
        state_code=state_code,
    )
    items = [to_prediction_dto(r) for r in records]
    meta = build_meta(
        dataset_version_ids=repo.get_dataset_version_ids(),
        model_run_id=model_run_id,
        filters={
            "model_run_id": str(model_run_id),
            "level": level,
            "state_code": state_code,
            "target_year": target_year,
            "territory_id": str(territory_id) if territory_id else None,
            "page": page,
            "page_size": page_size,
        },
    )
    return Page(items=items, page=page, page_size=page_size, total=total, meta=meta)
