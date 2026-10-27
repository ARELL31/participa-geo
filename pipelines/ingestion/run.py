"""Thin wrapper: run the ingestion pipeline through the single CLI.

Usage (from the repository root, inside the api container):

    python pipelines/ingestion/run.py --source-dir data/raw/ccpc \
        --output-dir data/processed

It forwards to ``participa_geo.cli`` so the ingestion logic lives in exactly one
place and is never duplicated here.
"""

from __future__ import annotations

import sys

from participa_geo.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["ingest", *sys.argv[1:]]))
