"""Readiness evaluation: ``database``, ``migrations``, ``dataset``, ``model``, ``gis``.

The checks run in order and short-circuit on the first database prerequisite that
fails (nothing downstream can be ready without the database). Results are cached
for a short TTL to avoid hammering the database and GeoServer. Every check catches
its own exceptions and returns ``False`` (never a trace or a credential).
"""

from __future__ import annotations

import time
import urllib.request

from sqlalchemy import text
from sqlalchemy.engine import Engine

HEALTH_CHECK_NAMES = ("database", "migrations", "dataset", "model", "gis")

_CACHE_TTL_S = 3.0
_GIS_TIMEOUT_S = 2.0


def build_readiness(settings, engine: Engine):
    """Return a ``() -> dict[str, bool]`` readiness evaluator."""
    gis_base = settings.gis_base_url.rstrip("/")
    state: dict = {"cached": None, "at": 0.0}

    def _db_ok() -> bool:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def _scalar_gt_zero(sql: str) -> bool:
        try:
            with engine.connect() as conn:
                return int(conn.execute(text(sql)).scalar()) > 0
        except Exception:
            return False

    def _gis_ok() -> bool:
        url = f"{gis_base}/wms?service=WMS&version=1.3.0&request=GetCapabilities"
        try:
            with urllib.request.urlopen(url, timeout=_GIS_TIMEOUT_S) as response:
                return response.status == 200
        except Exception:
            return False

    def evaluate() -> dict[str, bool]:
        now = time.monotonic()
        if state["cached"] is not None and now - state["at"] < _CACHE_TTL_S:
            return state["cached"]

        checks = {name: False for name in HEALTH_CHECK_NAMES}
        if not _db_ok():
            return _store(checks)
        checks["database"] = True
        if not _scalar_gt_zero("SELECT count(*) FROM alembic_version"):
            return _store(checks)
        checks["migrations"] = True
        if not _scalar_gt_zero("SELECT count(*) FROM observation"):
            return _store(checks)
        checks["dataset"] = True
        checks["model"] = _scalar_gt_zero("SELECT count(*) FROM model_run")
        checks["gis"] = _gis_ok()
        return _store(checks)

    def _store(checks: dict[str, bool]) -> dict[str, bool]:
        state["cached"] = checks
        state["at"] = time.monotonic()
        return checks

    return evaluate


__all__ = ["HEALTH_CHECK_NAMES", "build_readiness"]
