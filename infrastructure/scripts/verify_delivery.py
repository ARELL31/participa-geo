"""Verify a PARTICIPA-GEO ``technical.zip`` without any session-local paths.

    python infrastructure/scripts/verify_delivery.py --archive dist/hackathon/technical.zip

Checks forbidden members, the manifest, every declared SHA-256/size, the
CHECKSUMS file and (for complete packages) the required source/model/report
members. Exits 1 with a readable reason on failure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from participa_geo.reporting.delivery import DeliveryError, verify_archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a technical delivery ZIP.")
    parser.add_argument("--archive", required=True, help="Path to technical.zip.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the verification report as JSON (default: also JSON).",
    )
    args = parser.parse_args(argv)
    try:
        report = verify_archive(Path(args.archive))
    except DeliveryError as exc:
        print(f"delivery verification failed: {exc}")
        return 1
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
