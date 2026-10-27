"""Command-line entry point: ``python -m participa_geo.cli --help``.

Subcommands for ingestion, migration, training, GIS publication and delivery are
registered here. The single argparse parser is the integration point; wrappers
must not duplicate this logic.
"""

from __future__ import annotations

import argparse
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
