"""Alembic environment: run migrations against PostGIS as the ``migrator`` role.

The connection URL is never stored in a committed file. Precedence:

1. ``sqlalchemy.url`` set on the ``Config`` (the ``db migrate`` CLI and the test
   harness inject the migrator-role URL here).
2. The ``DB_*`` / ``DB_MIGRATOR_*`` environment variables (fallback).

The offline/online split follows the standard Alembic template.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from participa_geo.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_PLACEHOLDER = "driver://user:pass@localhost/dbname"


def _env_url() -> str:
    host = os.environ.get("DB_HOST", "db")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "participa_geo")
    user = os.environ.get("DB_MIGRATOR_USER", "migrator")
    password = os.environ.get("DB_MIGRATOR_PASSWORD", "")
    if not password:
        raise RuntimeError("DB_MIGRATOR_PASSWORD is not set; cannot run migrations")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"


def _database_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if not url or url == _PLACEHOLDER:
        return _env_url()
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
