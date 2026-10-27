"""``GET /gis/wms`` and ``GET /gis/wfs`` — bounded read-only GeoServer gateway."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from participa_geo.api.errors import problem
from participa_geo.api.gis_client import (
    GeoServerClient,
    GeoServerError,
    validate_wfs_request,
    validate_wms_request,
)

router = APIRouter()


def _gis_problem(request: Request) -> JSONResponse:
    detail = problem(
        status=503,
        code="unavailable",
        title="Servicio no disponible",
        detail="El servicio GIS no está disponible.",
        instance=request.url.path,
    )
    return JSONResponse(
        status_code=503,
        content=detail.model_dump(mode="json", exclude_none=True),
        media_type="application/problem+json",
    )


def _proxy(request: Request, service: str, validator) -> Response:
    params = validator(dict(request.query_params))
    client = GeoServerClient(request.app.state.settings.gis_base_url)
    try:
        status, content_type, body = client.forward(service, params)
    except GeoServerError:
        return _gis_problem(request)
    if status >= 400:
        return _gis_problem(request)
    media_type = content_type or (
        "application/xml" if service == "wms" else "application/json"
    )
    return Response(content=body, status_code=status, media_type=media_type)


@router.get("/gis/wms", tags=["gis"])
def gis_wms(request: Request) -> Response:
    return _proxy(request, "wms", validate_wms_request)


@router.get("/gis/wfs", tags=["gis"])
def gis_wfs(request: Request) -> Response:
    return _proxy(request, "wfs", validate_wfs_request)
