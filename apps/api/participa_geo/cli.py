"""Command-line entry point: ``python -m participa_geo.cli --help``.

Subcommands for ingestion, migration, GIS publication and delivery are
registered here. The single argparse parser is the integration point; wrappers
must not duplicate this logic.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from participa_geo import __version__


def _ingest(args: argparse.Namespace) -> int:
    from participa_geo.ingestion.pipeline import run_ingest

    result = run_ingest(
        Path(args.source_dir),
        Path(args.output_dir),
        sources=Path(args.sources),
        fetch=args.fetch,
    )
    print(
        f"ingested {result.observation_count} municipal observations "
        f"(aggregate sha256 {result.aggregate_sha256}) into {args.output_dir}"
    )
    return 0


def _db_migrate(args: argparse.Namespace) -> int:
    from participa_geo.db.session import run_migrations
    from participa_geo.settings import Settings

    settings = Settings()
    run_migrations(settings)
    print(f"migrated database {settings.db_name} to head")
    return 0


def _db_load(args: argparse.Namespace) -> int:
    from participa_geo.db.repository import Repository, read_processed_observations
    from participa_geo.db.session import session_scope, writer_engine
    from participa_geo.settings import Settings

    settings = Settings()
    processed_dir = Path(args.processed_dir)
    datasets, observations = read_processed_observations(processed_dir)

    with session_scope(writer_engine(settings)) as session:
        repo = Repository(session)
        for dataset in datasets:
            repo.upsert_dataset(dataset)
        count = repo.upsert_observations(observations)

    print(f"loaded {count} observations and {len(datasets)} dataset versions")
    return 0


def _gis_import(args: argparse.Namespace) -> int:
    from participa_geo.db.session import session_scope, writer_engine
    from participa_geo.settings import Settings
    from pipelines.validation.geography import import_reference

    settings = Settings()
    archive = Path(args.archive)
    with session_scope(writer_engine(settings)) as session:
        audit = import_reference(archive, session)

    print(
        f"imported {audit.reference_count} reference territories "
        f"({audit.source_crs} -> {audit.target_crs}) and "
        f"{audit.correspondence_count} correspondences; "
        f"rejected {audit.rejected_geometry_count} geometries"
    )
    return 0


def _gis_publish(args: argparse.Namespace) -> int:
    from gis.geoserver.bootstrap import publish_layers
    from participa_geo.settings import Settings

    settings = Settings()
    audit = publish_layers(settings)

    print(
        f"published {len(audit.layers)} layers in workspace {audit.workspace} "
        f"(WFS level {audit.wfs_service_level}, "
        f"transaction_enabled={audit.wfs_transaction_enabled}, "
        f"removed {len(audit.foreign_workspaces_removed)} foreign workspaces)"
    )
    return 0


def _gis_verify(args: argparse.Namespace) -> int:
    from gis.geoserver.bootstrap import verify_layers
    from participa_geo.settings import Settings

    settings = Settings()
    report = verify_layers(settings)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="participa_geo",
        description=(
            "PARTICIPA-GEO: comandos de ingestión de datos, migración, "
            "entrenamiento, publicación GIS y generación de entregables."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command")

    ingest = subparsers.add_parser(
        "ingest",
        help="Ingerir y agregar datos oficiales CCPC municipales.",
    )
    ingest.add_argument(
        "--source-dir",
        required=True,
        help="Directorio con los CSV verificados (p. ej. data/raw/ccpc).",
    )
    ingest.add_argument(
        "--output-dir",
        required=True,
        help="Directorio de artefactos procesados (p. ej. data/processed).",
    )
    ingest.add_argument(
        "--sources",
        default="data/sources.json",
        help="Manifiesto de fuentes verificadas (por defecto data/sources.json).",
    )
    ingest.add_argument(
        "--fetch",
        action="store_true",
        help="Obtener fuentes verificadas (ZIP completo) si faltan en source-dir.",
    )
    ingest.set_defaults(handler=_ingest)

    db = subparsers.add_parser("db", help="Operaciones de base de datos.")
    db_sub = db.add_subparsers(dest="db_command")

    db_migrate = db_sub.add_parser("migrate", help="Aplicar migraciones Alembic.")
    db_migrate.set_defaults(handler=_db_migrate)

    db_load = db_sub.add_parser(
        "load", help="Cargar observaciones procesadas en PostGIS."
    )
    db_load.add_argument(
        "--processed-dir",
        required=True,
        help="Directorio de artefactos procesados (p. ej. data/processed).",
    )
    db_load.set_defaults(handler=_db_load)

    gis = subparsers.add_parser("gis", help="Publicación y verificación GIS.")
    gis_sub = gis.add_subparsers(dest="gis_command")

    gis_import = gis_sub.add_parser("import", help="Importar geometría de referencia INE.")
    gis_import.add_argument(
        "--archive",
        required=True,
        help="ZIP de la cartografía INE (p. ej. data/raw/gis/ine-jalisco-2025-12-15.zip).",
    )
    gis_import.set_defaults(handler=_gis_import)

    gis_publish = gis_sub.add_parser("publish", help="Publicar capas WMS/WFS en GeoServer.")
    gis_publish.set_defaults(handler=_gis_publish)

    gis_verify = gis_sub.add_parser("verify", help="Verificar WMS/WFS de sólo lectura.")
    gis_verify.set_defaults(handler=_gis_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
