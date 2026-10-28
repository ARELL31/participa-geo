from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import UUID, uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

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
