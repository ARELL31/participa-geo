"""Delivery-package tests: allowlist/private exclusion and a real CLI build (T9)."""

from __future__ import annotations

import contextlib
import csv
import json
import urllib.request
import zipfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from participa_geo.reporting.delivery import (
    NATIONAL_RAW_SOURCE_MEMBERS,
    REQUIRED_NATIONAL_MEMBERS,
    SCENARIO_REPORT_MEMBERS,
    DeliveryContext,
    DeliveryError,
    ScenarioFacts,
    _candidate_files,
    build_technical_zip,
    load_delivery_context,
    verify_archive,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_national_raw_allowlist_includes_continuity_reconstruction_sources(tmp_path):
    root = tmp_path / "repo"
    members = (
        "data/raw/continuity/HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb",
        "data/raw/continuity/official-section-history.csv",
        "data/raw/continuity/district-headquarters.txt",
    )
    for member in members:
        _write(root / member, "source\n")

    included = {
        path.relative_to(root).as_posix()
        for path in _candidate_files(root, include_raw_sources=True, national=True)
    }
    omitted = {
        path.relative_to(root).as_posix()
        for path in _candidate_files(root, include_raw_sources=False, national=True)
    }

    assert set(members) <= set(NATIONAL_RAW_SOURCE_MEMBERS)
    assert set(members) <= included
    assert not (set(members) & omitted)


def test_national_delivery_includes_official_history_export_script(tmp_path):
    root = _complete_fixture_root(tmp_path)
    script = "scripts/export_official_section_history.sh"
    _write(root / script, "#!/bin/sh\nprintf 'fixture\\n'\n")
    archive = tmp_path / "complete.zip"

    build_technical_zip(
        load_delivery_context(),
        archive,
        root=root,
        strict=True,
        reports={
            "reports/methodology.pdf": b"%PDF-1.4\n",
            "reports/executive.pdf": b"%PDF-1.4\n",
            "reports/district-observations.csv": b"district,observed_year\n01,2024\n",
        },
    )

    with zipfile.ZipFile(archive) as package:
        assert script in package.namelist()


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "README.md", "# PARTICIPA-GEO\n")
    _write(root / "pyproject.toml", "[project]\nname='x'\n")
    _write(root / "uv.lock", "lock\n")
    _write(root / "compose.yaml", "services: {}\n")
    _write(root / ".env.example", "DB_API_PASSWORD=change-me-api\n")
    _write(root / ".dockerignore", ".env\n")
    _write(root / "infrastructure" / "docker" / "api.Dockerfile", "FROM scratch\n")
    _write(root / "infrastructure" / "docker" / "web.Dockerfile", "FROM scratch\n")
    init_script = root / "infrastructure" / "docker" / "db-init.sh"
    _write(init_script, "#!/bin/sh\n")
    init_script.chmod(0o755)
    _write(root / "tests" / "e2e" / "full-journey.spec.ts", "export {};\n")
    _write(root / ".github" / "workflows" / "ci.yml", "name: ci\n")
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
        assert ".env.example" in names
        assert ".dockerignore" in names
        assert "infrastructure/docker/api.Dockerfile" in names
        assert "infrastructure/docker/web.Dockerfile" in names
        assert "tests/e2e/full-journey.spec.ts" in names
        assert ".github/workflows/ci.yml" in names
        init_info = package.getinfo("infrastructure/docker/db-init.sh")
        assert (init_info.external_attr >> 16) & 0o111
        assert "dictionaries/history.csv" in names
        assert "MANIFEST.json" in names
        assert "CHECKSUMS.sha256" in names
        assert not any(name.startswith(".git/") for name in names)
        assert not any("node_modules" in name for name in names)
        assert not any("__pycache__" in name for name in names)
        assert not any(
            name == ".env" or (name.startswith(".env.") and name != ".env.example")
            for name in names
        )
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

    tampered = tmp_path / "tampered.zip"
    with (
        zipfile.ZipFile(archive) as source,
        zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as target,
    ):
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename == "README.md":
                payload = b"tampered\n"
            target.writestr(item, payload)

    with pytest.raises(DeliveryError):
        verify_archive(tampered)


def _complete_fixture_root(tmp_path: Path) -> Path:
    root = _fixture_root(tmp_path)
    generated_prefixes = ("dictionaries/", "sources/", "reports/", "data/raw/")
    for relative in REQUIRED_NATIONAL_MEMBERS:
        if relative.startswith(generated_prefixes):
            continue
        path = root / relative
        if not path.is_file():
            _write(path, "fixture\n")
    return root


def _scenario_context(context: DeliveryContext) -> DeliveryContext:
    facts = ScenarioFacts(
        scenario_id=UUID("9b2c5f1e-4d3a-4c6b-8e7f-1a2b3c4d5e6f"),
        model_run_id=context.model.model_run_id,
        model_sha256="0" * 64,
        input_sha256="1" * 64,
        target_year=2027,
        requested_reduction_pp=3.0,
        effective_reduction_pp=3.0,
        effective_reduction_min_pp=3.0,
        effective_reduction_max_pp=3.0,
        assumption_code="preventive_exploration",
        assumption_version="1.0",
        rationale_text="Supuesto de prueba revisado.",
        rules_version="scenario-rules-1.0.0",
        error_band_label=(
            "rango de error histórico de referencia trasladado condicionalmente; "
            "no es un intervalo causal"
        ),
        selected_count=1,
        risk_a_counts={"low": 1, "medium": 2, "high": 3, "insufficient": 4},
        risk_b_counts={"low": 1, "medium": 2, "high": 3, "insufficient": 4},
        risk_a_unstable=0,
        risk_b_unstable=0,
        baseline_mean=42.0,
        hypothetical_mean=39.0,
    )
    return replace(context, scenario=facts)


def test_clean_room_bootstrap_members_are_required(tmp_path):
    root = _complete_fixture_root(tmp_path)
    archive = tmp_path / "complete.zip"
    build_technical_zip(
        load_delivery_context(),
        archive,
        root=root,
        strict=True,
        reports={
            "reports/methodology.pdf": b"%PDF-1.4\n",
            "reports/executive.pdf": b"%PDF-1.4\n",
            "reports/district-observations.csv": b"district,observed_year\n01,2024\n",
        },
    )
    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
    for required in (
        ".env.example",
        ".dockerignore",
        "infrastructure/docker/api.Dockerfile",
        "infrastructure/docker/web.Dockerfile",
        "tests/e2e/full-journey.spec.ts",
        ".github/workflows/ci.yml",
    ):
        assert required in names

    (root / "infrastructure" / "docker" / "api.Dockerfile").unlink()
    with pytest.raises(DeliveryError, match="api.Dockerfile"):
        build_technical_zip(
            load_delivery_context(),
            tmp_path / "broken.zip",
            root=root,
            strict=True,
            reports={
                "reports/methodology.pdf": b"%PDF-1.4\n",
                "reports/executive.pdf": b"%PDF-1.4\n",
            },
        )


def test_complete_zip_requires_and_verifies_scenario_reports(tmp_path):
    root = _complete_fixture_root(tmp_path)
    context = _scenario_context(load_delivery_context())
    archive = tmp_path / "complete.zip"
    reports = {
        "reports/methodology.pdf": b"%PDF-1.4\n",
        "reports/executive.pdf": b"%PDF-1.4\n",
        "reports/district-observations.csv": b"district,observed_year\n01,2024\n",
        **{name: b"scenario-report\n" for name in SCENARIO_REPORT_MEMBERS},
    }
    manifest = build_technical_zip(
        context,
        archive,
        root=root,
        reports=reports,
        strict=True,
        include_raw_sources=False,
    )
    assert manifest.manifest["scenario_required"] is True
    assert "reports/scenario-map.png" in manifest.manifest["required_members"]
    assert verify_archive(archive)["complete"] is True

    broken = tmp_path / "broken.zip"
    with (
        zipfile.ZipFile(archive) as source,
        zipfile.ZipFile(broken, "w", compression=zipfile.ZIP_DEFLATED) as target,
    ):
        for item in source.infolist():
            if item.filename == "reports/scenario-map.png":
                continue
            target.writestr(item, source.read(item.filename))
    with pytest.raises(DeliveryError, match="scenario-map.png"):
        verify_archive(broken)


def test_verify_cli_fails_incomplete_unless_allowed(tmp_path):
    root = _fixture_root(tmp_path)
    archive = tmp_path / "incomplete.zip"
    build_technical_zip(load_delivery_context(), archive, root=root, strict=False)
    from participa_geo.cli import _verify_delivery

    assert _verify_delivery(SimpleNamespace(archive=str(archive), allow_incomplete=False)) == 1
    assert _verify_delivery(SimpleNamespace(archive=str(archive), allow_incomplete=True)) == 0


def test_deliver_requires_an_explicit_source_mode(tmp_path):
    from participa_geo.cli import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "deliver",
                "--scenario-id",
                "9b2c5f1e-4d3a-4c6b-8e7f-1a2b3c4d5e6f",
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
    parsed = parser.parse_args(
        [
            "deliver",
            "--scenario-id",
            "9b2c5f1e-4d3a-4c6b-8e7f-1a2b3c4d5e6f",
            "--output-dir",
            str(tmp_path / "out"),
            "--skip-sources",
        ]
    )
    assert parsed.skip_sources is True
    assert parsed.confirm_source_license is False


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


@pytest.mark.skipif(
    not (
        Path(__file__).resolve().parents[2]
        / "data/processed/gis/reference-2025-12-15.geojson"
    ).is_file(),
    reason=(
        "legacy scenario delivery requires the MVP reference GeoJSON; "
        "no synthetic geometry is substituted"
    ),
)
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
            source_mode="confirm",
        )

    archive = Path(summary["technical_zip"]["path"])
    assert archive.is_file()
    report = verify_archive(archive)
    assert report["complete"] is True
    assert report["team_slug"] == "participa-geo"
    assert report["source_mode"] == "confirm"

    import zipfile

    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
        for year in (2009, 2012, 2015, 2018, 2021, 2024):
            assert f"data/raw/ccpc/jalisco-{year}.csv" in names
        assert "data/raw/gis/ine-jalisco-2025-12-15.zip" in names
        assert "data/processed/model/model.json" in names
        assert "docs/hackathon/source-licenses.md" in names
        assert "docs/api/openapi.json" in names
        assert "sources/SOURCES.md" in names
        assert "sources/sources.json" in names
        source_info = json.loads(package.read("sources/sources.json"))
        assert source_info["source_mode"] == "confirm"
        assert source_info["raw_sources_included"] is True
        assert len(source_info["sources"]) == 6
        assert all(len(item["sha256"]) == 64 for item in source_info["sources"])
        assert "reports/methodology.pdf" in names
        assert "reports/executive.pdf" in names
        assert "reports/scenario.csv" in names
        assert "reports/scenario.geojson" in names
        assert "reports/scenario-map.png" in names
        assert not any(name.startswith(".git/") for name in names)
        assert not any("node_modules" in name for name in names)
        assert not any("cartas" in name for name in names)
        assert not any(
            name == ".env" or (name.startswith(".env.") and name != ".env.example")
            for name in names
        )

    scenario_csv = (tmp_path / "delivery" / "scenario.csv").read_text(encoding="utf-8-sig")
    assert "dataset_version_ids=[" in scenario_csv
    assert "# dataset_version_ids=[]" not in scenario_csv
    assert "# sources=" in scenario_csv
    assert "# kind=scenario_csv" in scenario_csv
    data_rows = [
        row
        for row in csv.DictReader(
            [line for line in scenario_csv.splitlines() if line and not line.startswith("#")]
        )
    ]
    insufficient = next(row for row in data_rows if row["baseline_abstention_pct"] == "")
    assert insufficient["effective_reduction_pp"] == ""

    scenario_geojson = json.loads(
        (tmp_path / "delivery" / "scenario.geojson").read_text(encoding="utf-8")
    )
    assert scenario_geojson["metadata"]["dataset_version_ids"]
    assert len(scenario_geojson["metadata"]["sources"]["sources"]) == 6
    null_feature = next(
        feature
        for feature in scenario_geojson["features"]
        if feature["properties"]["baseline_abstention_pct"] is None
    )
    assert null_feature["properties"]["effective_reduction_pp"] is None

    # A second delivery in skip mode must omit originals but remain complete.
    skip_summary = run_delivery(
        scenario_id,
        tmp_path / "delivery-skip",
        "participa-geo",
        settings=settings,
        source_mode="skip",
    )
    skip_archive = Path(skip_summary["technical_zip"]["path"])
    skip_report = verify_archive(skip_archive)
    assert skip_report["complete"] is True
    assert skip_report["source_mode"] == "skip"
    with zipfile.ZipFile(skip_archive) as package:
        skip_names = set(package.namelist())
        assert not any(name.startswith("data/raw/ccpc/") for name in skip_names)
        assert "data/raw/gis/ine-jalisco-2025-12-15.zip" not in skip_names
        assert "sources/SOURCES.md" in skip_names
        assert "sources/sources.json" in skip_names
        skip_info = json.loads(package.read("sources/sources.json"))
        assert skip_info["source_mode"] == "skip"
        assert skip_info["raw_sources_included"] is False
        assert len(skip_info["sources"]) == 6
        assert "docs/api/openapi.json" in skip_names
        assert any(name.startswith("reports/scenario") for name in skip_names)

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
