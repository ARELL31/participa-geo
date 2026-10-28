"""FastAPI application factory and middleware.

``create_app`` is the single entry point. There is deliberately no module-level
``app``: serving uses ``uvicorn participa_geo.main:create_app --factory`` so
that ``Settings`` (which requires secrets) is only resolved at startup, when the
container environment is populated. This also keeps ``import participa_geo.main``
side-effect free for tests.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException

from participa_geo.api.errors import register_exception_handlers, request_id_var
from participa_geo.api.readiness import build_readiness
from participa_geo.api.routes import (
    gis,
    health,
    history,
    models,
    municipality_districts,
    predictions,
    recommendations,
    reports,
    scenarios,
    summary,
    territories,
)
from participa_geo.db.session import api_engine
from participa_geo.reporting.store import ReportStore
from participa_geo.scenarios.service import ScenarioRateLimiter
from participa_geo.settings import Settings

API_PREFIX = "/api/v1"

_LOGGING_INTERNAL = {
    "args",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "taskName",
    "thread",
    "threadName",
}


class JsonFormatter(logging.Formatter):
    """JSON log lines with request_id; never emits credentials."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _LOGGING_INTERNAL and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("participa_geo")
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    root.propagate = False


_configure_logging()
logger = logging.getLogger("participa_geo.api")


class RequestContextMiddleware:
    """Assigns a request_id, echoes it as ``X-Request-ID`` and logs one JSON line."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = headers.get("x-request-id") or str(uuid4())
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status = [0]

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                status[0] = message["status"]
                MutableHeaders(scope=message)["x-request-id"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        finally:
            # Log while the contextvar still holds the id, and pass it explicitly
            # so the record is correct even if the formatter runs later.
            logger.info(
                "http_request",
                extra={
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status": status[0],
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )
            request_id_var.reset(token)


class JsonSizeLimitMiddleware:
    """Rejects request bodies larger than the configured limit with 413."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        received = 0
        max_bytes = 128 * 1024 if scope.get("path", "").endswith("/scenarios") else self.max_bytes

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > max_bytes:
                    raise StarletteHTTPException(
                        status_code=413,
                        detail=(
                            f"El cuerpo de la petición supera el límite de {max_bytes // 1024} KiB."
                        ),
                    )
            return message

        await self.app(scope, limited_receive, send)


def create_app(settings: Settings | None = None, *, readiness=None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="PARTICIPA-GEO API",
        version="0.1.0",
        description="Análisis municipal de participación electoral (Jalisco).",
    )
    app.state.settings = settings
    # The web process connects only as the least-privilege ``api`` role. The
    # engine is created lazily (no connection until a request/readiness probe).
    app.state.api_engine = api_engine(settings)
    app.state.readiness = readiness or build_readiness(settings, app.state.api_engine)
    # Process-local scenario limiter (10/min and one active request per client);
    # valid for the single-worker MVP only.
    app.state.scenario_rate_limiter = ScenarioRateLimiter()
    # Generated exports are written atomically under a git-ignored directory.
    # Institutional documents are only served if the CLI has published them.
    from participa_geo.reporting.delivery import repo_root

    reports_root = Path(settings.reports_dir)
    if not reports_root.is_absolute():
        reports_root = repo_root() / reports_root
    institutional_root = Path(settings.institutional_reports_dir)
    if not institutional_root.is_absolute():
        institutional_root = repo_root() / institutional_root
    app.state.report_store = ReportStore(
        reports_root,
        institutional_dir=institutional_root,
    )

    logging.getLogger("participa_geo").setLevel(settings.log_level.upper())

    # Order: request-context is outermost so every response (including 413)
    # carries a request id and is logged.
    app.add_middleware(JsonSizeLimitMiddleware, max_bytes=settings.json_max_bytes)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(health.router, prefix=f"{API_PREFIX}/health", tags=["health"])
    app.include_router(territories.router, prefix=API_PREFIX)
    app.include_router(municipality_districts.router, prefix=API_PREFIX)
    app.include_router(history.router, prefix=API_PREFIX)
    app.include_router(summary.router, prefix=API_PREFIX)
    app.include_router(models.router, prefix=API_PREFIX)
    app.include_router(predictions.router, prefix=API_PREFIX)
    app.include_router(scenarios.router, prefix=API_PREFIX)
    app.include_router(recommendations.router, prefix=API_PREFIX)
    app.include_router(gis.router, prefix=API_PREFIX)
    app.include_router(reports.router, prefix=API_PREFIX)

    return app
