"""Health endpoints: liveness and readiness.

Readiness evaluates injectable checks stored on ``app.state.health_checks``.
Until T2–T5 load data, migrations, the model and the GIS layer, every check
returns ``False`` and ``/api/v1/health/ready`` responds ``503`` with a
problem+json body carrying the ``checks`` extension.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from participa_geo.api.errors import problem

router = APIRouter()

HEALTH_CHECK_NAMES = ("database", "migrations", "dataset", "model", "gis")


class LiveStatus(BaseModel):
    status: str


@router.get("/live", response_model=LiveStatus)
async def live() -> LiveStatus:
    """The process responds; does not imply data is ready."""
    return LiveStatus(status="alive")


@router.get("/ready")
async def ready(request: Request):
    checks = request.app.state.health_checks
    results = {name: bool(checks[name]()) for name in HEALTH_CHECK_NAMES}
    if all(results.values()):
        return {"status": "ready", "checks": results}

    detail = problem(
        status=503,
        code="not_ready",
        title="Servicio no disponible",
        detail="El servicio no está listo: faltan prerequisitos.",
        instance=request.url.path,
        checks=results,
    )
    return JSONResponse(
        status_code=503,
        content=detail.model_dump(mode="json", exclude_none=True),
        media_type="application/problem+json",
    )
