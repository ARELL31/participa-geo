"""Export the FastAPI OpenAPI schema to ``docs/api/openapi.json``.

Run inside the api container:

    python infrastructure/scripts/export_openapi.py --output docs/api/openapi.json

The schema is generated from the live application factory, never hand-maintained.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from participa_geo.main import create_app
from participa_geo.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the OpenAPI contract.")
    parser.add_argument("--output", required=True, help="Destination JSON path.")
    args = parser.parse_args()

    # No secrets and no environment required: the factory builds routes lazily.
    settings = Settings(
        _env_file=None,
        db_api_password="export-only",
        gis_admin_password="export-only",
    )
    app = create_app(settings)
    schema = app.openapi()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {output} ({len(schema.get('paths', {}))} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
