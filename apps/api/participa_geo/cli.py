"""Command-line entry point: ``python -m participa_geo.cli --help``.

Subcommands for ingestion, migration, training, GIS publication and delivery are
registered by later tasks. The single argparse parser is the integration point;
wrappers must not duplicate it.
"""

from __future__ import annotations

import argparse

from participa_geo import __version__


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
