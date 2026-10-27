"""Integration tests over the PostGIS schema, data and role permissions.

These run against the isolated ``participa_geo_test`` database (see
``tests/integration/conftest.py``). The SQL column names fixed by the brief
(``territory_version``, ``reference_date``, ``geometry``) are asserted directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED = REPO_ROOT / "data" / "processed"


def _url(cfg: dict, user: str, password: str) -> str:
    return f"postgresql+psycopg://{user}:{password}@{cfg['host']}:{cfg['port']}/{cfg['db_name']}"


def test_reference_geometry_4326(postgis_session):
    count = postgis_session.scalar(
        text(
            """
            SELECT count(*) FROM territory_version
            WHERE reference_date = DATE '2025-12-15'
              AND geometry IS NOT NULL
              AND ST_SRID(geometry) = 4326 AND ST_IsValid(geometry)
            """
        )
    )
    assert count == 125


def test_reference_geometry_within_jalisco_bounds(postgis_session):
    outside = postgis_session.scalar(
        text(
            """
            SELECT count(*) FROM territory_version
            WHERE reference_date = DATE '2025-12-15'
              AND (
                ST_XMin(geometry) < -107 OR ST_XMax(geometry) > -100
                OR ST_YMin(geometry) < 18 OR ST_YMax(geometry) > 23
              )
            """
        )
    )
    assert outside == 0


def test_historical_geometry_is_null(postgis_session):
    count = postgis_session.scalar(
        text(
            """
            SELECT count(*) FROM territory_version
            WHERE origin_year IS NOT NULL AND geometry IS NULL
            """
        )
    )
    assert count == 750


def test_identity_not_footprint_equality(postgis_session):
    rows = postgis_session.execute(
        text(
            """
            SELECT identity_status, footprint_status, count(*)
            FROM territory_correspondence
            GROUP BY identity_status, footprint_status
            """
        )
    ).all()
    statuses = {(row[0], row[1]): row[2] for row in rows}
    assert statuses == {("verified_catalogue", "not_verified"): 750}


def test_observation_count_is_750(postgis_session):
    count = postgis_session.scalar(text("SELECT count(*) FROM observation"))
    assert count == 750


def test_same_import_is_idempotent(postgis_session, gis_archive):
    from pipelines.validation.geography import import_reference

    before_ref = postgis_session.scalar(
        text(
            "SELECT count(*) FROM territory_version "
            "WHERE reference_date = DATE '2025-12-15'"
        )
    )
    before_corr = postgis_session.scalar(
        text("SELECT count(*) FROM territory_correspondence")
    )
    import_reference(gis_archive, postgis_session)
    postgis_session.commit()
    after_ref = postgis_session.scalar(
        text(
            "SELECT count(*) FROM territory_version "
            "WHERE reference_date = DATE '2025-12-15'"
        )
    )
    after_corr = postgis_session.scalar(
        text("SELECT count(*) FROM territory_correspondence")
    )
    assert before_ref == after_ref == 125
    assert before_corr == after_corr == 750


def test_observation_load_is_idempotent(postgis_session):
    from participa_geo.db.repository import Repository, read_processed_observations

    before = postgis_session.scalar(text("SELECT count(*) FROM observation"))
    datasets, observations = read_processed_observations(PROCESSED)
    repo = Repository(postgis_session)
    for dataset in datasets:
        repo.upsert_dataset(dataset)
    repo.upsert_observations(observations)
    postgis_session.commit()
    after = postgis_session.scalar(text("SELECT count(*) FROM observation"))
    assert before == after == 750


def test_api_role_cannot_insert(postgis_session, db_config):
    engine = create_engine(
        _url(db_config, db_config["api_user"], db_config["api_password"])
    )
    with pytest.raises(DBAPIError) as exc_info:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO dataset_version "
                    "(id, year, source_url, member, sha256, encoding) VALUES "
                    "('00000000-0000-0000-0000-000000000001'::uuid, 2000, "
                    "'x', 'x', 'x', 'utf-8-sig')"
                )
            )
    engine.dispose()
    assert "permission denied" in str(exc_info.value).lower()


def test_gis_role_cannot_update(postgis_session, db_config):
    engine = create_engine(
        _url(db_config, db_config["gis_reader_user"], db_config["gis_reader_password"])
    )
    with pytest.raises(DBAPIError) as exc_info:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE territory_version SET name = 'x' WHERE false")
            )
    engine.dispose()
    assert "permission denied" in str(exc_info.value).lower()
