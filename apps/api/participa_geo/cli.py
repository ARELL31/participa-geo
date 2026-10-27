"""Command-line entry point: ``python -m participa_geo.cli --help``.

Subcommands for ingestion, migration, GIS publication and delivery are
registered here. The single argparse parser is the integration point; wrappers
must not duplicate this logic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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


def _train(args: argparse.Namespace) -> int:
    from participa_geo.db.repository import read_processed_observations
    from participa_geo.db.session import session_scope, writer_engine
    from participa_geo.prediction.cohorts import read_identity_statuses
    from participa_geo.prediction.training import train_release
    from participa_geo.settings import Settings

    settings = Settings()
    _, observations = read_processed_observations(Path(args.processed_dir))

    with session_scope(writer_engine(settings)) as session:
        identity_statuses = read_identity_statuses(session)

    bundle = train_release(
        observations,
        Path(args.output_dir),
        identity_statuses=identity_statuses,
    )

    print(
        f"trained family {bundle.family} (model_run_id {bundle.model_run_id}): "
        f"{bundle.candidate_count} candidates and "
        f"{bundle.total_count} prediction records written to {args.output_dir}"
    )
    return 0


def _model_load(args: argparse.Namespace) -> int:
    from participa_geo.db.repository import load_model_bundle
    from participa_geo.db.session import session_scope, writer_engine
    from participa_geo.settings import Settings

    settings = Settings()
    bundle_dir = Path(args.bundle_dir)
    with session_scope(writer_engine(settings)) as session:
        model_run_id = load_model_bundle(bundle_dir, session)

    print(f"loaded model {model_run_id} from {bundle_dir}")
    return 0


def _write_atomic(path: Path, payload: bytes) -> None:
    """Write one delivery file through a same-directory temporary file."""
    from uuid import uuid4

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".tmp-{uuid4().hex}"
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_delivery(
    scenario_id,
    output_dir: Path,
    team_slug: str,
    *,
    settings=None,
    source_mode: str,
) -> dict:
    """Generate the institutional documents, maps and technical package.

    ``source_mode`` is ``"confirm"`` only after the human confirmed the source
    redistribution terms (raw CSVs/GIS ZIP included) or ``"skip"`` (checksum/URL
    package without original files). There is no implicit/safe-by-accident mode.

    This is the implementation shared by the CLI and the integration test. It
    fails explicitly (no placeholder) when a real GeoServer A/B map cannot be
    obtained.
    """
    if source_mode not in {"confirm", "skip"}:
        raise ValueError("source_mode debe ser 'confirm' o 'skip'")
    from participa_geo.api.gis_client import GeoServerClient
    from participa_geo.api.schemas.reports import MEDIA_TYPE_BY_FORMAT
    from participa_geo.db.session import api_engine, session_scope
    from participa_geo.reporting.delivery import (
        build_technical_zip,
        load_delivery_context,
        repo_root,
        verify_archive,
    )
    from participa_geo.reporting.geojson import export_scenario_geojson
    from participa_geo.reporting.maps import render_scenario_map
    from participa_geo.reporting.pdf import (
        generate_executive,
        generate_methodology,
        generate_scenario_pdf,
    )
    from participa_geo.reporting.store import ReportStore
    from participa_geo.reporting.tables import export_scenario_csv
    from participa_geo.scenarios.service import ScenarioService
    from participa_geo.settings import Settings

    settings = settings or Settings()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with session_scope(api_engine(settings)) as session:
        scenario = ScenarioService(session).get(scenario_id)
        if scenario is None:
            raise SystemExit(f"scenario {scenario_id} does not exist")

    context = load_delivery_context(scenario=scenario)
    sources = _delivery_sources(context)
    meta_csv = _delivery_meta(context, report_kind="scenario_csv")
    meta_geojson = _delivery_meta(context, report_kind="scenario_geojson")

    methodology = generate_methodology(context)
    executive = generate_executive(context)
    scenario_csv = export_scenario_csv(scenario, meta_csv, sources=sources)
    reference = repo_root() / "data" / "processed" / "gis" / "reference-2025-12-15.geojson"
    scenario_geojson = export_scenario_geojson(
        scenario, reference, meta_geojson, sources=sources
    )
    scenario_pdf = generate_scenario_pdf(scenario, meta_csv, context=context)
    gis_client = GeoServerClient(settings.gis_base_url, timeout=5.0)
    map_png = render_scenario_map(scenario, "png", client=gis_client)
    map_pdf = render_scenario_map(scenario, "pdf", client=gis_client)

    reports = {
        "reports/methodology.pdf": methodology,
        "reports/executive.pdf": executive,
        "reports/scenario.csv": scenario_csv,
        "reports/scenario.geojson": scenario_geojson,
        "reports/scenario.pdf": scenario_pdf,
        "reports/scenario-map.png": map_png,
        "reports/scenario-map.pdf": map_pdf,
    }
    for arcname, payload in reports.items():
        _write_atomic(output_dir / Path(arcname).name, payload)

    archive = output_dir / "technical.zip"
    built = build_technical_zip(
        context,
        archive,
        root=repo_root(),
        reports=reports,
        strict=True,
        team_slug=team_slug,
        include_raw_sources=source_mode == "confirm",
    )
    verification = verify_archive(archive)
    summary = {
        "team_slug": team_slug,
        "scenario_id": str(scenario.scenario_id),
        "model_run_id": str(scenario.model_run_id),
        "output_dir": str(output_dir),
        "source_mode": source_mode,
        "technical_zip": {
            "path": str(archive),
            "sha256": built.sha256,
            "size_bytes": built.size_bytes,
            "file_count": built.file_count,
        },
        "verification": verification,
        "files": {
            name: {
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "media_type": MEDIA_TYPE_BY_FORMAT[
                    "pdf"
                    if name.endswith(".pdf")
                    else "png"
                    if name.endswith(".png")
                    else "geojson"
                    if name.endswith(".geojson")
                    else "csv"
                ],
            }
            for name, payload in reports.items()
        },
    }
    _write_atomic(
        output_dir / "DELIVERY.json",
        (
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
    )

    reports_root = Path(settings.reports_dir)
    if not reports_root.is_absolute():
        reports_root = repo_root() / reports_root
    institutional_root = Path(settings.institutional_reports_dir)
    if not institutional_root.is_absolute():
        institutional_root = repo_root() / institutional_root
    store = ReportStore(reports_root, institutional_dir=institutional_root)
    store.publish_institutional(
        "methodology_pdf",
        methodology,
        filename="methodology.pdf",
        media_type=MEDIA_TYPE_BY_FORMAT["pdf"],
        sources={
            "scenario_id": str(scenario.scenario_id),
            "model_run_id": str(scenario.model_run_id),
            "source_mode": source_mode,
        },
        model_run_id=scenario.model_run_id,
        scenario_id=scenario.scenario_id,
    )
    store.publish_institutional(
        "executive_pdf",
        executive,
        filename="executive.pdf",
        media_type=MEDIA_TYPE_BY_FORMAT["pdf"],
        sources={
            "scenario_id": str(scenario.scenario_id),
            "model_run_id": str(scenario.model_run_id),
            "source_mode": source_mode,
        },
        model_run_id=scenario.model_run_id,
        scenario_id=scenario.scenario_id,
    )
    store.publish_institutional(
        "technical_zip",
        archive.read_bytes(),
        filename="technical.zip",
        media_type=MEDIA_TYPE_BY_FORMAT["zip"],
        sources={
            "scenario_id": str(scenario.scenario_id),
            "model_run_id": str(scenario.model_run_id),
            "source_mode": source_mode,
        },
        model_run_id=scenario.model_run_id,
        scenario_id=scenario.scenario_id,
    )
    return summary


def _delivery_sources(context) -> dict:
    """Source/model metadata carried by the CLI scenario exports."""
    return {
        "sources": [
            {
                "year": source.year,
                "source_url": source.source_url,
                "member": source.member,
                "sha256": source.sha256,
                "municipality_count": source.municipality_count,
            }
            for source in context.sources
        ],
        "model": {
            "family": context.model.family,
            "model_run_id": str(context.model.model_run_id),
            "data_aggregate_sha256": context.data_aggregate_sha256,
            "reference_date": context.reference_date,
            "versions": context.versions,
        },
    }


def _delivery_meta(context, *, report_kind: str):
    from participa_geo.api.metadata import build_meta

    filters: dict = {"report_kind": report_kind}
    if context.scenario is not None:
        filters["scenario_id"] = str(context.scenario.scenario_id)
        filters["target_year"] = context.scenario.target_year
    return build_meta(
        dataset_version_ids=list(context.dataset_version_ids),
        model_run_id=context.model.model_run_id,
        reference_date=context.reference_date,
        generated_at=context.generated_at,
        geographic_warning=(
            "Referencia cartográfica INE 2025-12-15. No implica igualdad de "
            "límites históricos (footprint_status=not_verified)."
        ),
        filters=filters,
    )


def _deliver(args: argparse.Namespace) -> int:
    from uuid import UUID

    try:
        scenario_id = UUID(args.scenario_id)
    except ValueError:
        print("scenario-id debe ser un UUID")
        return 2
    if args.confirm_source_license:
        source_mode = "confirm"
    elif args.skip_sources:
        source_mode = "skip"
    else:  # argparse requires one; defensive for direct Namespace construction
        print(
            "deliver requiere --confirm-source-license o --skip-sources. "
            "No se incluyen fuentes sin confirmación explícita."
        )
        return 2
    summary = run_delivery(
        scenario_id,
        Path(args.output_dir),
        args.team_slug,
        source_mode=source_mode,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def _verify_delivery(args: argparse.Namespace) -> int:
    from participa_geo.reporting.delivery import DeliveryError, verify_archive

    try:
        report = verify_archive(Path(args.archive))
    except DeliveryError as exc:
        print(f"delivery verification failed: {exc}")
        return 1
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    if not report.get("complete") and not getattr(args, "allow_incomplete", False):
        print(
            "delivery verification failed: el paquete está incompleto; "
            "use --allow-incomplete sólo para diagnóstico."
        )
        return 1
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

    train = subparsers.add_parser(
        "train",
        help="Entrenar el modelo interpretable y escribir los artefactos.",
    )
    train.add_argument(
        "--processed-dir",
        required=True,
        help="Directorio de artefactos procesados (p. ej. data/processed).",
    )
    train.add_argument(
        "--output-dir",
        required=True,
        help="Directorio de artefactos del modelo (p. ej. data/processed/model).",
    )
    train.set_defaults(handler=_train)

    model = subparsers.add_parser(
        "model",
        help="Cargar los artefactos de un modelo ya entrenado en PostGIS.",
    )
    model_sub = model.add_subparsers(dest="model_command")

    model_load = model_sub.add_parser(
        "load", help="Cargar el bundle de artefactos (modelo + predicciones)."
    )
    model_load.add_argument(
        "--bundle-dir",
        required=True,
        help="Directorio de artefactos del modelo (p. ej. data/processed/model).",
    )
    model_load.set_defaults(handler=_model_load)

    deliver = subparsers.add_parser(
        "deliver",
        help="Generar reportes institucionales, mapas y el paquete técnico.",
    )
    deliver.add_argument(
        "--scenario-id",
        required=True,
        help="UUID de un escenario persistido y elegible.",
    )
    deliver.add_argument(
        "--output-dir",
        required=True,
        help="Directorio de entrega (p. ej. dist/hackathon).",
    )
    deliver.add_argument(
        "--team-slug",
        default="participa-geo",
        help="Identificador del equipo en el manifiesto (por defecto participa-geo).",
    )
    source_group = deliver.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--confirm-source-license",
        action="store_true",
        help=(
            "Confirmar que se revisaron las condiciones de redistribución y que "
            "se incluyen los seis CSV y el ZIP GIS originales en el paquete."
        ),
    )
    source_group.add_argument(
        "--skip-sources",
        action="store_true",
        help=(
            "No incluir los CSV/ZIP originales; el paquete llevará únicamente "
            "URLs, checksums y el archivo de fuentes."
        ),
    )
    deliver.set_defaults(handler=_deliver)

    verify_delivery = subparsers.add_parser(
        "verify-delivery",
        help="Verificar manifiesto, miembros y checksums de un paquete técnico.",
    )
    verify_delivery.add_argument(
        "--archive",
        required=True,
        help="Ruta del technical.zip a verificar.",
    )
    verify_delivery.add_argument(
        "--allow-incomplete",
        action="store_true",
        help=(
            "Permitir que un paquete marcado como incompleto salga con código 0 "
            "(sólo diagnóstico; nunca para entrega)."
        ),
    )
    verify_delivery.set_defaults(handler=_verify_delivery)

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
