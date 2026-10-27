"""Shared fixtures for the PostGIS/GeoServer integration tests.

A dedicated test database (``participa_geo_test``, owned by ``migrator`` and
created by ``db-init.sh``) is migrated and loaded once per test session. The
fixture only touches that database (never the demo database or a SQLite file),
and it resets its own schema before migrating.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_DB = "participa_geo_test"
GIS_ARCHIVE = REPO_ROOT / "data" / "raw" / "gis" / "ine-jalisco-2025-12-15.zip"
PROCESSED = REPO_ROOT / "data" / "processed"

VIEWS = ["municipalities", "participation_history", "predictions", "scenario_results"]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _url(cfg: dict, user: str, password: str, db: str | None = None) -> str:
    db = db or cfg["db_name"]
    return f"postgresql+psycopg://{user}:{password}@{cfg['host']}:{cfg['port']}/{db}"


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
    }


@pytest.fixture(scope="session")
def gis_archive() -> Path:
    return GIS_ARCHIVE


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
