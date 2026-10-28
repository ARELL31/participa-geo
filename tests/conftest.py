"""Shared pytest fixtures for the PARTICIPA-GEO API.

The API is exercised through ``create_app`` with an explicit ``Settings`` so the
tests never depend on ambient environment variables or a real ``.env`` file.

PostGIS fixtures (``db_config``, ``gis_archive``, ``postgis_session``) set up a
dedicated test database (``participa_geo_test``) once per session. They live here
at the test root so the HTTP contract tests, the integration tests and the unit
tests all share one source of truth.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

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
NATIONAL_PROCESSED = PROCESSED / "national"
MODEL_DIR = NATIONAL_PROCESSED / "model"

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
        # These migration-created tables are outside Base.metadata. Drop them
        # before SQLAlchemy orders drops from its incomplete metadata graph.
        conn.execute(text("DROP TABLE IF EXISTS fact_ccpc_section CASCADE"))
        for table in (
            "geo_section",
            "geo_district_2023",
            "geo_municipality",
            "geo_state",
        ):
            conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        Base.metadata.drop_all(conn)

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", migrator_url)
    command.upgrade(cfg, "head")

    # Seed the isolated test database from the checked-in national artifacts.
    # This preserves Jalisco's state-14 contract values without depending on
    # absent Jalisco-only processed/model files or the shared GeoServer DB.
    from participa_geo.db.repository import Repository, read_national_municipal_observations
    from participa_geo.territory import TerritoryKey, territory_id

    writer_url = _url(db_config, db_config["writer_user"], db_config["writer_password"])
    writer_engine = create_engine(writer_url, future=True)
    with Session(writer_engine) as session:
        ingest = json.loads((NATIONAL_PROCESSED / "national-ingest.json").read_text())
        dataset_rows = [
            {
                "id": member["dataset_version_id"],
                "year": source["year"],
                "state_code": member["state_code"],
                "source_url": source["source_url"],
                "member": member["member"],
                "sha256": member["sha256"],
                "encoding": "utf-8-sig",
            }
            for source in ingest["sources"]
            for member in source["csv_members"]
            if member["state_code"] is not None
        ]
        session.execute(
            text("""
                INSERT INTO dataset_version
                    (id, year, state_code, source_url, member, sha256, encoding)
                VALUES (:id, :year, :state_code, :source_url, :member, :sha256, :encoding)
            """),
            dataset_rows,
        )
        observations = read_national_municipal_observations(NATIONAL_PROCESSED)
        repo = Repository(session)
        repo.upsert_observations(observations)

        reference_by_key = {}
        for observation in observations:
            key = (observation.key.state_code, observation.key.municipality_code)
            reference_by_key.setdefault(key, observation.municipality_name)
        reference_ids = {
            key: territory_id(TerritoryKey("municipality", key[0], key[1]))
            for key in reference_by_key
        }
        session.execute(
            text("""
                INSERT INTO territory_version
                    (id, system, state_code, level, territory_code, municipality_code,
                     district_plan, name, reference_date, origin_year, geometry,
                     source_srid, provenance)
                VALUES (:id, 'ine', :state_code, 'municipality', :code, :code,
                        NULL, :name, :reference_date, NULL, NULL, NULL,
                        'national contract test reference')
            """),
            [
                {
                    "id": reference_ids[key],
                    "state_code": key[0],
                    "code": key[1],
                    "name": name,
                    "reference_date": date(2025, 12, 15),
                }
                for key, name in reference_by_key.items()
            ],
        )
        correspondences = []
        from participa_geo.ingestion.schema import observation_id

        for observation in observations:
            origin_id = observation_id(
                observation.key.state_code,
                observation.key.municipality_code,
                observation.year,
                observation.source_version_id,
            )
            reference_id = reference_ids[
                (observation.key.state_code, observation.key.municipality_code)
            ]
            correspondences.append(
                {
                    "id": uuid5(NAMESPACE_URL, f"correspondence:{origin_id}:{reference_id}"),
                    "origin_id": origin_id,
                    "reference_id": reference_id,
                }
            )
        session.execute(
            text("""
                INSERT INTO territory_correspondence
                    (id, origin_territory_id, reference_territory_id, relation_type,
                     identity_status, footprint_status, evidence)
                VALUES (:id, :origin_id, :reference_id, 'same',
                        'verified_catalogue', 'not_verified', '{"source":"national test fixture"}')
            """),
            correspondences,
        )
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
