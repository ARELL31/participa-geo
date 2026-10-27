"""Shared pytest fixtures for the PARTICIPA-GEO API.

The API is exercised through ``create_app`` with an explicit ``Settings`` so the
tests never depend on ambient environment variables or a real ``.env`` file.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from participa_geo.main import create_app
from participa_geo.settings import Settings


def _test_settings() -> Settings:
    """A valid Settings for tests (no dependency on process environment)."""
    return Settings(
        _env_file=None,
        db_api_password="test-api-password",
        gis_admin_password="test-gis-password",
    )


@pytest.fixture
def settings() -> Settings:
    return _test_settings()


@pytest.fixture
def client_without_dataset():
    """TestClient whose readiness checks are all unsatisfied (no dataset loaded).

    In T1 no database, migrations, dataset, model or GIS layer exist yet, so
    ``/api/v1/health/ready`` must report 503 with ``checks.dataset == False``.
    """
    app = create_app(_test_settings())
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client_with_validation_route():
    """TestClient with a throwaway body-validating route to exercise 422.

    T1 has no business POST endpoints yet; this probe route lets the contract
    test assert the problem+json shape returned on ``RequestValidationError``.
    """
    from pydantic import BaseModel, ConfigDict

    class _Probe(BaseModel):
        model_config = ConfigDict(extra="forbid")
        value: int

    app = create_app(_test_settings())

    @app.post("/api/v1/probe")
    async def probe(body: _Probe) -> dict:
        return {"ok": body.value}

    with TestClient(app) as client:
        yield client
