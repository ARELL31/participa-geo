"""``GET /recommendations`` — versioned, neutral preventive rules (T6)."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request

from participa_geo.api.deps import SessionDep
from participa_geo.api.errors import ProblemException, problem
from participa_geo.api.metadata import build_meta
from participa_geo.api.schemas.common import Page
from participa_geo.api.schemas.models import TargetYearQuery
from participa_geo.api.schemas.scenarios import RecommendationDTO
from participa_geo.db.models import PredictionRecord
from participa_geo.db.repository import Repository
from participa_geo.recommendations.rules import (
    RECOMMENDATION_RULES_VERSION,
    recommend,
)

router = APIRouter()


def to_recommendation_dto(record: PredictionRecord) -> RecommendationDTO:
    return RecommendationDTO(
        territory_id=record.territory_id,
        municipality_code=record.municipality_code,
        municipality_name=record.municipality_name,
        target_year=record.target_year,
        risk=record.risk or "insufficient",
        risk_unstable=record.risk_unstable,
        eligible=record.eligible,
        model_run_id=record.model_run_id,
        rules_version=RECOMMENDATION_RULES_VERSION,
        recommendations=recommend(record),
    )


@router.get(
    "/recommendations",
    response_model=Page[RecommendationDTO],
    tags=["recommendations"],
)
def list_recommendations(
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
) -> Page[RecommendationDTO]:
    if len(request.query_params.getlist("level")) > 1:
        raise ProblemException(
            problem(
                status=422,
                code="validation_error",
                title="Parámetros no válidos",
                detail="El nivel debe especificarse una sola vez.",
                instance=request.url.path,
            )
        )
    if level == "federal_district":
        raise ProblemException(
            problem(
                status=409,
                code="district_model_unavailable",
                title="Modelo distrital no disponible",
                detail=(
                    "Sólo hay observaciones distritales de 2024; "
                    "no hay recomendaciones predictivas."
                ),
                instance=request.url.path,
            )
        )

    repo = Repository(session)
    published_model_run_id = repo.get_published_model_run_id()
    if published_model_run_id is None:
        raise ProblemException(
            problem(
                status=409,
                code="conflict",
                title="Estado en conflicto",
                detail="No se ha cargado ningún modelo municipal nacional.",
                instance=request.url.path,
            )
        )
    if model_run_id is None:
        model_run_id = published_model_run_id
    elif model_run_id != published_model_run_id:
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
    items = [to_recommendation_dto(record) for record in records]
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
