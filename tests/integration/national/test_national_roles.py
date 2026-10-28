"""Least-privilege contracts for national database roles."""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

NATIONAL_DATA_TABLES = (
    "dataset_version",
    "territory_version",
    "fact_ccpc_section",
    "observation",
    "model_run",
    "prediction",
)
AGGREGATE_TABLES = ("agg_municipality_district_year",)
GIS_TABLES = (
    "geo_state",
    "geo_municipality",
    "geo_district_2023",
    "geo_section",
    "geo_state_national_view",
    "geo_municipality_national_view",
    "geo_district_2023_national_view",
)


def _engine(db_config: dict, user_key: str, password_key: str):
    url = (
        f"postgresql+psycopg://{db_config[user_key]}:{db_config[password_key]}"
        f"@{db_config['host']}:{db_config['port']}/{db_config['db_name']}"
    )
    return create_engine(url)


def _privilege(db_config: dict, role: str, table: str, privilege: str) -> bool:
    engine = _engine(db_config, "migrator_user", "migrator_password")
    try:
        with engine.connect() as connection:
            return bool(
                connection.scalar(
                    text("SELECT has_table_privilege(:role, :table, :privilege)"),
                    {"role": role, "table": table, "privilege": privilege},
                )
            )
    finally:
        engine.dispose()


def test_api_is_read_only_on_national_source_and_result_tables(db_config: dict) -> None:
    for table in NATIONAL_DATA_TABLES:
        assert not _privilege(db_config, "api", table, "INSERT"), table
        assert not _privilege(db_config, "api", table, "UPDATE"), table


def test_api_can_read_national_aggregates(db_config: dict, postgis_session) -> None:
    engine = _engine(db_config, "api_user", "api_password")
    try:
        with engine.connect() as connection:
            for table in AGGREGATE_TABLES:
                assert connection.scalar(text(f"SELECT count(*) FROM {table}")) is not None
    finally:
        engine.dispose()


def test_gis_reader_is_select_only_and_cannot_update_territories(
    db_config: dict, postgis_session
) -> None:
    for table in (*NATIONAL_DATA_TABLES, *AGGREGATE_TABLES, *GIS_TABLES):
        for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
            assert not _privilege(db_config, "gis_reader", table, privilege), (
                table,
                privilege,
            )
    assert _privilege(db_config, "gis_reader", "geo_state", "SELECT")

    engine = _engine(db_config, "gis_reader_user", "gis_reader_password")
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("UPDATE territory_version SET name = name WHERE false"))
    except DBAPIError as exc:
        assert "permission denied" in str(exc).lower()
    else:
        raise AssertionError("gis_reader unexpectedly updated territory_version")
    finally:
        engine.dispose()


def test_gis_reader_can_select_a_national_map_layer(db_config: dict, postgis_session) -> None:
    engine = _engine(db_config, "gis_reader_user", "gis_reader_password")
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM geo_state_national_view")) >= 0
    finally:
        engine.dispose()


def test_writer_can_write_aggregates_but_not_migrate_or_administer(db_config: dict) -> None:
    for table in AGGREGATE_TABLES:
        assert _privilege(db_config, "writer", table, "INSERT"), table
        assert _privilege(db_config, "writer", table, "UPDATE"), table
        assert _privilege(db_config, "writer", table, "DELETE"), table

    assert not _privilege(db_config, "writer", "alembic_version", "UPDATE")
    engine = _engine(db_config, "writer_user", "writer_password")
    try:
        with engine.connect() as connection:
            assert not connection.scalar(
                text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
            )
            assert not connection.scalar(
                text(
                    "SELECT rolsuper OR rolcreaterole OR rolcreatedb "
                    "FROM pg_roles WHERE rolname=current_user"
                )
            )
    finally:
        engine.dispose()
