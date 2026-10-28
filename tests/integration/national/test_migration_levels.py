from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from participa_geo.db.models import Base

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_migration_backfills_legacy_rows_without_changing_ids(db_config: dict) -> None:
    url = (
        f"postgresql+psycopg://{db_config['migrator_user']}:{db_config['migrator_password']}"
        f"@{db_config['host']}:{db_config['port']}/{db_config['db_name']}"
    )
    schema = f"migration_levels_{uuid4().hex}"
    territory_id = UUID("0e488ee8-21b7-5ab4-850b-890b45ee6112")
    observation_id = UUID("e4080eb8-ddc9-5ae3-a9e0-e9e8e4432a90")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            connection.execute(
                text(
                    "CREATE TABLE territory_version (id uuid PRIMARY KEY, state_code varchar(2) "
                    "NOT NULL, municipality_code varchar(3) NOT NULL, name text NOT NULL)"
                )
            )
            connection.execute(
                text("CREATE TABLE observation (id uuid PRIMARY KEY, year integer NOT NULL)")
            )
            for table in ("model_run", "prediction", "scenario", "scenario_result"):
                connection.execute(text(f"CREATE TABLE {table} (id uuid PRIMARY KEY)"))
            connection.execute(
                text(
                    "INSERT INTO territory_version (id, state_code, municipality_code, name) "
                    "VALUES (:id, '14', '001', 'Guadalajara')"
                ),
                {"id": territory_id},
            )
            connection.execute(
                text("INSERT INTO observation (id, year) VALUES (:id, 2024)"),
                {"id": observation_id},
            )

            migration_path = REPO_ROOT / "alembic/versions/0004_national_levels.py"
            spec = importlib.util.spec_from_file_location("migration_0004", migration_path)
            migration = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(migration)
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()

            assert (
                connection.scalar(
                    text("SELECT id FROM territory_version WHERE municipality_code = '001'")
                )
                == territory_id
            )
            assert connection.scalar(text("SELECT id FROM observation")) == observation_id
            assert (
                connection.scalar(
                    text(
                        "SELECT level || ':' || territory_code || ':' || "
                        "COALESCE(district_plan, 'NULL') "
                        "FROM territory_version WHERE id = :id"
                    ),
                    {"id": territory_id},
                )
                == "municipality:001:NULL"
            )
            assert (
                connection.scalar(
                    text("SELECT level FROM observation WHERE id = :id"), {"id": observation_id}
                )
                == "municipality"
            )
            connection.execute(text("SET LOCAL search_path TO public"))
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    finally:
        engine.dispose()


def test_actual_alembic_chain_from_empty_schema_preserves_legacy_identity(
    db_config: dict,
) -> None:
    url = URL.create(
        "postgresql+psycopg",
        username=db_config["migrator_user"],
        password=db_config["migrator_password"],
        host=db_config["host"],
        port=db_config["port"],
        database=db_config["db_name"],
    )
    schema = f"alembic_chain_{uuid4().hex}"
    legacy_id = UUID("04b17993-9658-5de8-b594-b96c8f116a93")
    engine = create_engine(url)
    original_schemas = {table: table.schema for table in Base.metadata.tables.values()}
    try:
        for table in Base.metadata.tables.values():
            table.schema = schema
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        config = Config(str(REPO_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
        config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
        with engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{schema}", public'))
            connection.dialect.default_schema_name = schema
            config.attributes["connection"] = connection
            config.attributes["version_table_schema"] = schema
            command.upgrade(config, "0003")
            connection.commit()

            connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            # Revision 0001 materializes current metadata in this codebase. Remove
            # its later-level fields to reproduce the actual 0003/MVP table shape
            # immediately before running revision 0004.
            connection.execute(
                text(
                    "ALTER TABLE territory_version DROP COLUMN level CASCADE, "
                    "DROP COLUMN territory_code CASCADE, DROP COLUMN district_plan CASCADE, "
                    "DROP COLUMN valid_from CASCADE, DROP COLUMN valid_to CASCADE"
                )
            )
            connection.execute(
                text("ALTER TABLE territory_version ALTER COLUMN municipality_code SET NOT NULL")
            )
            for table in ("observation", "model_run", "prediction", "scenario", "scenario_result"):
                connection.execute(
                    text(
                        f"ALTER TABLE {table} DROP COLUMN level CASCADE, "
                        "DROP COLUMN district_plan CASCADE"
                    )
                )
            connection.execute(
                text(
                    "INSERT INTO territory_version "
                    "(id, system, state_code, municipality_code, name, reference_date, provenance) "
                    "VALUES (:id, 'ine', '14', '001', 'Guadalajara', "
                    "DATE '2025-12-15', 'legacy-test')"
                ),
                {"id": legacy_id},
            )
            connection.commit()

            command.upgrade(config, "head")
            connection.commit()
            row = connection.execute(
                text(
                    "SELECT id, level, territory_code, district_plan "
                    "FROM territory_version WHERE id = :id"
                ),
                {"id": legacy_id},
            ).one()
            assert row.id == legacy_id
            assert (row.level, row.territory_code, row.district_plan) == (
                "municipality",
                "001",
                None,
            )
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0005"
            assert connection.scalar(
                text(
                    "SELECT relkind FROM pg_class "
                    "WHERE oid = 'fact_ccpc_section'::regclass"
                )
            ) == "p"
            assert connection.scalar(
                text(
                    "SELECT has_table_privilege('writer', 'fact_ccpc_section', 'TRUNCATE')"
                )
            ) is True
            assert connection.scalar(
                text(
                    "SELECT has_table_privilege('writer', 'fact_ccpc_section', 'INSERT')"
                )
            ) is True
            assert connection.scalar(
                text(
                    "SELECT has_table_privilege('api', 'fact_ccpc_section', 'SELECT')"
                )
            ) is False
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
        for table, original_schema in original_schemas.items():
            table.schema = original_schema
