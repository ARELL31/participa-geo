"""Delivery-package tests: allowlist/private exclusion and a real CLI build (T9)."""

from __future__ import annotations

import contextlib
import json
import urllib.request
from pathlib import Path

import pytest

from participa_geo.reporting.delivery import (
    DeliveryError,
    build_technical_zip,
    load_delivery_context,
    verify_archive,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "README.md", "# PARTICIPA-GEO\n")
    _write(root / "pyproject.toml", "[project]\nname='x'\n")
    _write(root / "uv.lock", "lock\n")
    _write(root / "compose.yaml", "services: {}\n")
    _write(root / "data" / "sources.json", "{}\n")
    _write(root / "docs" / "hackathon" / "source-licenses.md", "# licencias\n")
    _write(root / "docs" / "hackathon" / "delivery-checklist.md", "# checklist\n")
    _write(root / "reports" / "methodology.pdf", "%PDF-1.4\n")
    _write(root / "reports" / "executive.pdf", "%PDF-1.4\n")
    _write(root / "apps" / "api" / "participa_geo" / "ok.py", "VALUE = 1\n")
    _write(root / "apps" / "web" / "src" / "ok.ts", "export const x = 1;\n")
    _write(root / "pipelines" / "ok.py", "VALUE = 2\n")
    _write(root / "gis" / "styles" / "ok.sld", "<xml/>\n")

    # Files that must never enter the technical package.
    _write(root / ".env", "DB_API_PASSWORD=secret\n")
    _write(root / "cartas" / "carta_cesion.pdf", "private\n")
    _write(root / "secrets" / "token.txt", "secret\n")
    _write(root / "apps" / "web" / "node_modules" / "pkg" / "index.js", "x\n")
    _write(root / ".git" / "config", "secret\n")
    _write(root / "apps" / "api" / "participa_geo" / "__pycache__" / "x.pyc", "x\n")
    _write(root / "apps" / "api" / "participa_geo" / "credentials.json", "{}\n")
    return root


def test_technical_zip_excludes_private_files(tmp_path):
    root = _fixture_root(tmp_path)
    context = load_delivery_context()
    archive = tmp_path / "technical.zip"
    manifest = build_technical_zip(
        context,
        archive,
        root=root,
        strict=False,
        reports={
            "reports/methodology.pdf": root / "reports" / "methodology.pdf",
            "reports/executive.pdf": root / "reports" / "executive.pdf",
        },
    )
    assert manifest.archive == archive
    assert manifest.sha256
    assert archive.is_file()

    import zipfile

    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        assert "apps/api/participa_geo/ok.py" in names
        assert "apps/web/src/ok.ts" in names
        assert "README.md" in names
        assert "dictionaries/history.csv" in names
        assert "MANIFEST.json" in names
        assert "CHECKSUMS.sha256" in names
        assert not any(name.startswith(".git/") for name in names)
        assert not any("node_modules" in name for name in names)
        assert not any("__pycache__" in name for name in names)
        assert not any(name == ".env" or name.startswith(".env.") for name in names)
        assert not any("cartas" in name for name in names)
        assert not any("credential" in name.lower() for name in names)
        assert not any("secret" in name.lower() for name in names)

    report = verify_archive(archive)
    assert report["complete"] is False
    assert report["file_count"] > 5


def test_verify_detects_tampered_member(tmp_path):
    root = _fixture_root(tmp_path)
    archive = tmp_path / "technical.zip"
    build_technical_zip(
        load_delivery_context(),
        archive,
        root=root,
        strict=False,
        reports={
            "reports/methodology.pdf": root / "reports" / "methodology.pdf",
            "reports/executive.pdf": root / "reports" / "executive.pdf",
        },
    )

    import zipfile

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(
        tampered, "w", compression=zipfile.ZIP_DEFLATED
    ) as target:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename == "README.md":
                payload = b"tampered\n"
            target.writestr(item, payload)

    with pytest.raises(DeliveryError):
        verify_archive(tampered)


def _settings(db_config: dict, tmp_path: Path):
    from participa_geo.settings import Settings

    return Settings(
        _env_file=None,
        db_host=db_config["host"],
        db_port=db_config["port"],
        db_name=db_config["db_name"],
        db_api_user=db_config["api_user"],
        db_api_password=db_config["api_password"],
        db_writer_user=db_config["writer_user"],
        db_writer_password=db_config["writer_password"],
        db_migrator_user=db_config["migrator_user"],
        db_migrator_password=db_config["migrator_password"],
        db_gis_reader_user=db_config["gis_reader_user"],
        db_gis_reader_password=db_config["gis_reader_password"],
        gis_admin_user=db_config["gis_admin_user"],
        gis_admin_password=db_config["gis_admin_password"],
        gis_base_url=db_config["gis_base_url"],
        reports_dir=str(tmp_path / "reports"),
        institutional_reports_dir=str(tmp_path / "reports" / "institutional"),
    )


def _point_geoserver_at(settings) -> None:
    import base64

    payload = json.dumps(
        {
            "dataStore": {
                "name": "participa_geo",
                "type": "PostGIS",
                "enabled": True,
                "connectionParameters": {
                    "entry": [
                        {"@key": "dbtype", "$": "postgis"},
                        {"@key": "host", "$": settings.db_host},
                        {"@key": "port", "$": str(settings.db_port)},
                        {"@key": "database", "$": settings.db_name},
                        {"@key": "schema", "$": "public"},
                        {"@key": "user", "$": settings.db_gis_reader_user},
                        {"@key": "passwd", "$": settings.db_gis_reader_password},
                        {"@key": "validate connections", "$": "true"},
                    ]
                },
            }
        }
    ).encode("utf-8")
    token = base64.b64encode(
        f"{settings.gis_admin_user}:{settings.gis_admin_password}".encode()
    ).decode("ascii")
    request = urllib.request.Request(
        f"{settings.gis_base_url}/rest/workspaces/participa_geo/datastores/participa_geo",
        data=payload,
        method="PUT",
        headers={"Content-Type": "application/json", "Authorization": f"Basic {token}"},
    )
    with urllib.request.urlopen(request, timeout=15.0) as response:
        assert response.status in (200, 201)


@contextlib.contextmanager
def _geoserver_database(settings):
    from gis.geoserver.bootstrap import publish_layers

    publish_layers(settings)
    try:
        yield
    finally:
        from participa_geo.settings import Settings

        _point_geoserver_at(Settings())


def test_cli_delivery_builds_verified_package_with_real_scenario(
    db_api_client, db_config, tmp_path
):
    from participa_geo.cli import run_delivery
    from participa_geo.reporting.delivery import verify_archive

    response = db_api_client.get("/api/v1/predictions", params={"page_size": 125})
    assert response.status_code == 200
    prediction = next(
        item
        for item in response.json()["items"]
        if item["eligible"] and item["estimated_abstention_pct"] is not None
    )
    created = db_api_client.post(
        "/api/v1/scenarios",
        json={
            "model_run_id": prediction["model_run_id"],
            "target_year": 2027,
            "territory_ids": [prediction["territory_id"]],
            "reduction_pp": 3.0,
            "assumption_code": "preventive_exploration",
        },
    )
    assert created.status_code == 201, created.text
    scenario_id = created.json()["scenario_id"]

    settings = _settings(db_config, tmp_path)
    with _geoserver_database(settings):
        summary = run_delivery(
            scenario_id,
            tmp_path / "delivery",
            "participa-geo",
            settings=settings,
            include_sources=True,
        )

    archive = Path(summary["technical_zip"]["path"])
    assert archive.is_file()
    report = verify_archive(archive)
    assert report["complete"] is True
    assert report["team_slug"] == "participa-geo"

    import zipfile

    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
        for year in (2009, 2012, 2015, 2018, 2021, 2024):
            assert f"data/raw/ccpc/jalisco-{year}.csv" in names
        assert "data/raw/gis/ine-jalisco-2025-12-15.zip" in names
        assert "data/processed/model/model.json" in names
        assert "docs/hackathon/source-licenses.md" in names
        assert "reports/methodology.pdf" in names
        assert "reports/executive.pdf" in names
        assert "reports/scenario-map.png" in names
        assert not any(name.startswith(".git/") for name in names)
        assert not any("node_modules" in name for name in names)
        assert not any("cartas" in name for name in names)
        assert not any(name == ".env" or name.startswith(".env.") for name in names)

    assert (tmp_path / "delivery" / "methodology.pdf").is_file()
    assert (tmp_path / "delivery" / "executive.pdf").is_file()
    assert (tmp_path / "delivery" / "scenario-map.png").stat().st_size > 10_000
    institutional = tmp_path / "reports" / "institutional" / "manifest.json"
    assert institutional.is_file()
    manifest = json.loads(institutional.read_text(encoding="utf-8"))
    assert set(manifest["entries"]) >= {
        "methodology_pdf",
        "executive_pdf",
        "technical_zip",
    }
