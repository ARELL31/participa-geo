"""Thin wrapper: run the training pipeline through the single CLI.

Usage (from the repository root, inside the api container):

    python pipelines/training/run.py --processed-dir data/processed \
        --output-dir data/processed/model

It forwards to ``participa_geo.cli`` so the training logic lives in exactly one
place and is never duplicated here.
"""

from __future__ import annotations

import sys

from participa_geo.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["train", *sys.argv[1:]]))
