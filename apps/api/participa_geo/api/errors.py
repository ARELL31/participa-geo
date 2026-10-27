"""Problem-details (RFC 7807) contract and exception handlers.

Every error response uses ``application/problem+json`` with the stable fields
``type, title, status, detail, instance, code, request_id``. Extensions (such as
the readiness ``checks`` map) are allowed. No stack traces, SQL or credentials
ever reach the response body.
"""

from __future__ import annotations

import contextvars
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("participa_geo.api")

ERROR_TYPE_PREFIX = "urn:participa-geo:error:"

#: Request id shared by the request middleware, handlers and JSON logs.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

_HTTP_TITLES: dict[int, tuple[str, str]] = {
    400: ("bad_request", "Petición inválida"),
    404: ("not_found", "Recurso no encontrado"),
    405: ("method_not_allowed", "Método no permitido"),
    409: ("conflict", "Estado en conflicto"),
    413: ("payload_too_large", "Cuerpo demasiado grande"),
    503: ("unavailable", "Servicio no disponible"),
}


class ProblemDetail(BaseModel):
    """A RFC 7807 problem-details body with the contract's stable fields."""

    model_config = ConfigDict(extra="allow")

    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None
    code: str
    request_id: str | None = None


class ProblemException(Exception):
    """Exception carrying a fully-formed :class:`ProblemDetail`."""

    def __init__(self, detail: ProblemDetail):
        super().__init__(detail.detail)
        self.detail = detail


def problem(
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    instance: str | None = None,
    request_id: str | None = None,
    **extensions: Any,
) -> ProblemDetail:
    request_id = request_id or request_id_var.get()
    return ProblemDetail(
        type=f"{ERROR_TYPE_PREFIX}{code}",
        title=title,
        status=status,
        detail=detail,
        instance=instance,
        code=code,
        request_id=request_id,
        **extensions,
    )


def _problem_response(detail: ProblemDetail, status_code: int | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code or detail.status,
        content=detail.model_dump(mode="json", exclude_none=True),
        media_type="application/problem+json",
    )


def _validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    return [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
        for err in exc.errors()
    ]


def register_exception_handlers(app: FastAPI) -> None:
    """Register the problem+json handlers for the whole application."""

    @app.exception_handler(ProblemException)
    async def problem_exception_handler(request: Request, exc: ProblemException):
        return _problem_response(exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = _validation_errors(exc)
        detail = problem(
            status=422,
            code="validation_error",
            title="Validación fallida",
            detail="La entrada no supera la validación de esquema.",
            instance=request.url.path,
            errors=errors,
        )
        return _problem_response(detail)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        code, title = _HTTP_TITLES.get(exc.status_code, ("http_error", "Error HTTP"))
        detail_text = exc.detail if isinstance(exc.detail, str) else "Error de petición."
        detail = problem(
            status=exc.status_code,
            code=code,
            title=title,
            detail=detail_text,
            instance=request.url.path,
        )
        return _problem_response(detail, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(
            "unhandled_error path=%s", request.url.path, exc_info=exc
        )
        detail = problem(
            status=500,
            code="internal_error",
            title="Error interno",
            detail="Se produjo un error interno inesperado.",
            instance=request.url.path,
        )
        return _problem_response(detail, status_code=500)
