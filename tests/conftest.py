"""Shared pytest fixtures for the PARTICIPA-GEO API.

The API is exercised through ``create_app`` with an explicit ``Settings`` so the
tests never depend on ambient environment variables or a real ``.env`` file.

PostGIS fixtures (``db_config``, ``gis_archive``, ``postgis_session``) set up a
dedicated test database (``participa_geo_test``) once per session. They live here
at the test root so the HTTP contract tests, the integration tests and the unit
tests all share one source of truth.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from participa_geo.main import create_app
from participa_geo.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_DB = "participa_geo_test"
GIS_ARCHIVE = REPO_ROOT / "data" / "raw" / "gis" / "ine-jalisco-2025-12-15.zip"
PROCESSED = REPO_ROOT / "data" / "processed"
MODEL_DIR = REPO_ROOT / "data" / "processed" / "model"

VIEWS = ["municipalities", "participation_history", "predictions", "scenario_results"]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _test_settings() -> Settings:
    """A valid Settings for tests (no dependency on process environment)."""
    return Settings(
        _env_file=None,
        db_api_password="test-api-password",
        gis_admin_password="test-gis-password",
    )


def _url(cfg: dict, user: str, password: str, db: str | None = None) -> str:
    db = db or cfg["db_name"]
    return f"postgresql+psycopg://{user}:{password}@{cfg['host']}:{cfg['port']}/{db}"


# ---------------------------------------------------------------------------
# Basic HTTP fixtures (no database)
# ---------------------------------------------------------------------------


@pytest.fixture
def settings() -> Settings:
    return _test_settings()


@pytest.fixture
def api_client():
    """TestClient with no database/GIS dependency (unit-level validation)."""
    app = create_app(_test_settings())
    with TestClient(app) as client:
        yield client


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


# ---------------------------------------------------------------------------
# PostGIS fixtures (migrate + load the isolated test database)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def db_config() -> dict:
    return {
        "host": _env("DB_HOST", "db"),
        "port": int(_env("DB_PORT", "5432")),
        "db_name": TEST_DB,
        "migrator_user": _env("DB_MIGRATOR_USER", "migrator"),
        "migrator_password": _env("DB_MIGRATOR_PASSWORD"),
        "writer_user": _env("DB_WRITER_USER", "writer"),
        "writer_password": _env("DB_WRITER_PASSWORD"),
        "api_user": _env("DB_API_USER", "api"),
        "api_password": _env("DB_API_PASSWORD"),
        "gis_reader_user": _env("DB_GIS_READER_USER", "gis_reader"),
        "gis_reader_password": _env("DB_GIS_READER_PASSWORD"),
        "gis_admin_user": _env("GIS_ADMIN_USER", "admin"),
        "gis_admin_password": _env("GIS_ADMIN_PASSWORD"),
        "gis_base_url": _env("GIS_BASE_URL", "http://geoserver:8080/geoserver"),
    }


@pytest.fixture(scope="session")
def gis_archive() -> Path:
    return GIS_ARCHIVE


@pytest.fixture(scope="session")
def delivery_context():
    """Real delivery context derived from the T2/T4 artifacts (T9)."""
    from participa_geo.reporting.delivery import load_delivery_context

    return load_delivery_context(MODEL_DIR, PROCESSED)


@pytest.fixture(scope="session")
def postgis_session(db_config: dict):
    """Migrate and load the test database, yielding a migrator ``Session``."""
    from participa_geo.db.models import Base

    migrator_url = _url(db_config, db_config["migrator_user"], db_config["migrator_password"])
    engine = create_engine(migrator_url, future=True)

    with engine.begin() as conn:
        for view in VIEWS:
            conn.execute(text(f"DROP VIEW IF EXISTS {view} CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        Base.metadata.drop_all(conn)

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", migrator_url)
    command.upgrade(cfg, "head")

    # Load observations + reference geometry as the writer role.
    from participa_geo.db.repository import Repository, read_processed_observations
    from pipelines.validation.geography import import_reference

    writer_url = _url(db_config, db_config["writer_user"], db_config["writer_password"])
    writer_engine = create_engine(writer_url, future=True)
    with Session(writer_engine) as session:
        datasets, observations = read_processed_observations(PROCESSED)
        repo = Repository(session)
        for dataset in datasets:
            repo.upsert_dataset(dataset)
        repo.upsert_observations(observations)
        import_reference(GIS_ARCHIVE, session)
        session.commit()
    writer_engine.dispose()

    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(scope="session")
def loaded_model_run_id(db_config: dict, postgis_session):
    """Load the T4 model artifacts into the test database (writer role)."""
    from participa_geo.db.repository import load_model_bundle
    from participa_geo.db.session import writer_engine

    settings = Settings(
        _env_file=None,
        db_host=db_config["host"],
        db_port=db_config["port"],
        db_name=db_config["db_name"],
        db_writer_user=db_config["writer_user"],
        db_writer_password=db_config["writer_password"],
        db_api_user=db_config["api_user"],
        db_api_password=db_config["api_password"],
        gis_admin_user=db_config["gis_admin_user"],
        gis_admin_password=db_config["gis_admin_password"],
    )
    engine = writer_engine(settings)
    with Session(engine) as session:
        run_id = load_model_bundle(MODEL_DIR, session)
        session.commit()
    engine.dispose()
    return run_id


@pytest.fixture
def db_api_client(db_config: dict, postgis_session, loaded_model_run_id):
    """TestClient backed by the migrated/loaded test database (api role)."""
    settings = Settings(
        _env_file=None,
        db_host=db_config["host"],
        db_port=db_config["port"],
        db_name=db_config["db_name"],
        db_api_user=db_config["api_user"],
        db_api_password=db_config["api_password"],
        gis_admin_user=db_config["gis_admin_user"],
        gis_admin_password=db_config["gis_admin_password"],
        gis_base_url=db_config["gis_base_url"],
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client
