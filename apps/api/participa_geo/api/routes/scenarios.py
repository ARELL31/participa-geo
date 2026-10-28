"""``POST /scenarios`` and ``GET /scenarios/{id}`` (T6)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, status

from participa_geo.api.deps import SessionDep
from participa_geo.api.errors import ProblemException, problem
from participa_geo.api.schemas.scenarios import ScenarioDTO, ScenarioRequest
from participa_geo.scenarios.rules import ScenarioConflictError, ScenarioInputError
from participa_geo.scenarios.service import (
    ScenarioRateLimiter,
    ScenarioRateLimitError,
    ScenarioService,
)

router = APIRouter()


def _client_key(request: Request) -> str:
    # No authentication in the MVP; the limiter is scoped to the caller's socket
    # address. A reverse proxy deployment would need trusted forwarded headers.
    return request.client.host if request.client else "unknown"


def _validation_problem(request: Request, exc: ScenarioInputError) -> ProblemException:
    return ProblemException(
        problem(
            status=422,
            code="validation_error",
            title="Validación fallida",
            detail="La solicitud de escenario no supera la validación.",
            instance=request.url.path,
            errors=exc.errors,
        )
    )


def _conflict_problem(request: Request, exc: ScenarioConflictError) -> ProblemException:
    return ProblemException(
        problem(
            status=409,
            code="conflict",
            title="Estado en conflicto",
            detail=str(exc),
            instance=request.url.path,
        )
    )


def _rate_limit_problem(request: Request, exc: ScenarioRateLimitError) -> ProblemException:
    detail = (
        "Ya hay una solicitud de escenario en curso para este cliente."
        if exc.active
        else "Se alcanzó el límite de 10 creaciones de escenario por minuto."
    )
    return ProblemException(
        problem(
            status=429,
            code="rate_limited",
            title="Demasiadas solicitudes",
            detail=detail,
            instance=request.url.path,
            retry_after_seconds=exc.retry_after_seconds,
        )
    )


@router.post(
    "/scenarios",
    response_model=ScenarioDTO,
    status_code=status.HTTP_201_CREATED,
    tags=["scenarios"],
)
def create_scenario(
    request: Request,
    body: ScenarioRequest,
    *,
    session: SessionDep,
) -> ScenarioDTO:
    if body.level == "federal_district":
        raise ProblemException(
            problem(
                status=409,
                code="district_model_unavailable",
                title="Escenarios distritales no disponibles",
                detail=("Sólo hay observaciones distritales de 2024; no existe escenario 2027."),
                instance=request.url.path,
            )
        )
    limiter: ScenarioRateLimiter = request.app.state.scenario_rate_limiter
    try:
        with limiter.acquire(_client_key(request)):
            try:
                return ScenarioService(session).create(body)
            except ScenarioInputError as exc:
                raise _validation_problem(request, exc) from None
            except ScenarioConflictError as exc:
                raise _conflict_problem(request, exc) from None
    except ScenarioRateLimitError as exc:
        raise _rate_limit_problem(request, exc) from None


@router.get(
    "/scenarios/{scenario_id}",
    response_model=ScenarioDTO,
    tags=["scenarios"],
)
def get_scenario(
    request: Request,
    scenario_id: UUID,
    *,
    session: SessionDep,
) -> ScenarioDTO:
    scenario = ScenarioService(session).get(scenario_id)
    if scenario is None:
        raise ProblemException(
            problem(
                status=404,
                code="not_found",
                title="Recurso no encontrado",
                detail="El recurso solicitado no existe.",
                instance=request.url.path,
            )
        )
    return scenario
