"""Database engine and session helpers.

Every connection is scoped to a least-privilege role:

- ``migrator`` — runs Alembic migrations and owns the schema.
- ``writer``   — loads observations, reference geometry and results.
- ``api``      — read-only service role (the web process).
- ``gis_reader`` — read-only role used by GeoServer.

The API web process never uses the migrator/writer/gis_reader roles; those are
available to the maintenance CLI and the integration tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from participa_geo.settings import Settings


def database_url(
    settings: Settings,
    *,
    user: str,
    password: str,
    db_name: str | None = None,
) -> str:
    """Build a ``postgresql+psycopg`` URL for a specific role."""
    name = db_name or settings.db_name
    return (
        f"postgresql+psycopg://{user}:{password}"
        f"@{settings.db_host}:{settings.db_port}/{name}"
    )


def engine_for(
    settings: Settings, *, user: str, password: str, db_name: str | None = None
) -> Engine:
    return create_engine(
        database_url(settings, user=user, password=password, db_name=db_name),
        pool_pre_ping=True,
        future=True,
    )


def migrator_engine(settings: Settings, db_name: str | None = None) -> Engine:
    if not settings.db_migrator_password:
        raise RuntimeError("DB_MIGRATOR_PASSWORD is not set")
    return engine_for(
        settings, user=settings.db_migrator_user, password=settings.db_migrator_password,
        db_name=db_name,
    )


def writer_engine(settings: Settings, db_name: str | None = None) -> Engine:
    if not settings.db_writer_password:
        raise RuntimeError("DB_WRITER_PASSWORD is not set")
    return engine_for(
        settings, user=settings.db_writer_user, password=settings.db_writer_password,
        db_name=db_name,
    )


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Yield a ``Session`` and commit/rollback around the block."""
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def run_migrations(settings: Settings, db_name: str | None = None) -> None:
    """Apply Alembic migrations as the ``migrator`` role (idempotent)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path("alembic.ini")))
    cfg.set_main_option(
        "sqlalchemy.url",
        database_url(
            settings,
            user=settings.db_migrator_user,
            password=settings.db_migrator_password,
            db_name=db_name,
        ),
    )
    command.upgrade(cfg, "head")


__all__ = [
    "database_url",
    "engine_for",
    "migrator_engine",
    "run_migrations",
    "session_scope",
    "writer_engine",
]
