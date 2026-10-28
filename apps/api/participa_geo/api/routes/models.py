"""``GET /models`` and ``GET /models/{id}`` — persisted, already-trained runs."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request

from participa_geo.api.deps import SessionDep
from participa_geo.api.errors import ProblemException, problem
from participa_geo.api.metadata import build_meta
from participa_geo.api.schemas.common import Page
from participa_geo.api.schemas.models import ModelDTO
from participa_geo.db.models import ModelRecord
from participa_geo.db.repository import Repository

router = APIRouter()


def to_model_dto(record: ModelRecord) -> ModelDTO:
    parameters = record.parameters or {}
    cut_dates = record.cut_dates or {}
    return ModelDTO(
        model_run_id=record.model_run_id,
        family=record.family,
        level=record.level,
        district_plan=record.district_plan,
        target_year=int(cut_dates.get("target_year", 2027)),
        reference_date=str(cut_dates.get("reference_date", "2025-12-15")),
        features=list(record.features or []),
        parameters=parameters,
        cut_dates=record.cut_dates,
        hashes=record.hashes,
        metrics=record.metrics,
        exclusions=record.exclusions,
        limitations=list(parameters.get("limitations", [])),
        created_at=record.created_at,
    )


@router.get("/models", response_model=Page[ModelDTO], tags=["models"])
def list_models(
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 25,
    level: Literal["municipality", "federal_district"] = "municipality",
    *,
    session: SessionDep,
) -> Page[ModelDTO]:
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
        raise _district_model_unavailable(request)
    repo = Repository(session)
    records, total = repo.get_models(page=page, page_size=page_size)
    items = [to_model_dto(r) for r in records]
    model_run_id = records[0].model_run_id if records else None
    meta = build_meta(
        dataset_version_ids=repo.get_dataset_version_ids(),
        model_run_id=model_run_id,
        filters={"level": level, "page": page, "page_size": page_size},
    )
    return Page(items=items, page=page, page_size=page_size, total=total, meta=meta)


@router.get("/models/{model_run_id}", response_model=ModelDTO, tags=["models"])
def get_model(
    model_run_id: UUID,
    request: Request,
    level: Literal["municipality", "federal_district"] = "municipality",
    *,
    session: SessionDep,
) -> ModelDTO:
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
        raise _district_model_unavailable(request)
    record = Repository(session).get_model(model_run_id)
    if record is None:
        raise ProblemException(
            problem(
                status=404,
                code="not_found",
                title="Recurso no encontrado",
                detail="El recurso solicitado no existe.",
                instance=request.url.path,
            )
        )
    return to_model_dto(record)


def _district_model_unavailable(request: Request) -> ProblemException:
    return ProblemException(
        problem(
            status=409,
            code="district_model_unavailable",
            title="Modelo distrital no disponible",
            detail="No hay un modelo predictivo distrital publicado.",
            instance=request.url.path,
        )
    )
