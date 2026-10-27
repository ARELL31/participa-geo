"""Integration tests for persisted scenarios and their traceable side effects (T6).

Covers the full HTTP cycle against PostGIS, a restart (new app/client instance),
atomic rollback, the no-recalculation read path, and the GeoServer GetFeature /
GetMap path filtered by scenario UUID.
"""

from __future__ import annotations

import base64
import hashlib
import json
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from participa_geo.main import create_app
from participa_geo.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = REPO_ROOT / "data" / "processed" / "model"


def _settings(db_config: dict) -> Settings:
    return Settings(
        _env_file=None,
        db_host=db_config["host"],
        db_port=db_config["port"],
        db_name=db_config["db_name"],
        db_api_user=db_config["api_user"],
        db_api_password=db_config["api_password"],
        gis_admin_user=db_config["gis_admin_user"],
        gis_admin_password=db_config["gis_admin_password"],
        gis_base_url=db_config["gis_base_url"],
    )


def _point_geoserver_at(settings: Settings) -> None:
    """Point the published PostGIS datastore at one database (test/restore)."""
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
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {token}",
        },
    )
    with urllib.request.urlopen(request, timeout=15.0) as response:
        assert response.status in (200, 201)


@contextmanager
def _geoserver_database(settings: Settings):
    """Temporarily serve the isolated test DB, then restore the demo datastore."""
    _point_geoserver_at(settings)
    try:
        yield
    finally:
        _point_geoserver_at(Settings())



def _new_client(db_config: dict) -> TestClient:
    app = create_app(_settings(db_config))
    return TestClient(app)


def _predictions(client: TestClient) -> list[dict]:
    response = client.get("/api/v1/predictions", params={"page_size": 125})
    assert response.status_code == 200
    return response.json()["items"]


def _eligible(items: list[dict]) -> list[dict]:
    return [
        p
        for p in items
        if p["eligible"] and p["estimated_abstention_pct"] is not None
    ]


def _create(client: TestClient, *, selected: list[str], reduction: float = 3.0) -> dict:
    items = _predictions(client)
    body = {
        "model_run_id": items[0]["model_run_id"],
        "target_year": 2027,
        "territory_ids": selected,
        "reduction_pp": reduction,
        "assumption_code": "preventive_exploration",
    }
    response = client.post("/api/v1/scenarios", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scenario_survives_api_restart_and_keeps_125_results(db_config, db_api_client):
    items = _predictions(db_api_client)
    selected = [p["territory_id"] for p in _eligible(items)[:3]]

    created = _create(db_api_client, selected=selected)
    assert len(created["results"]) == 125

    # A brand-new application/client (new engine, same database) reads the
    # persisted scenario without recalculating it.
    restarted = _new_client(db_config)
    fetched = restarted.get(f"/api/v1/scenarios/{created['scenario_id']}")

    assert fetched.status_code == 200
    assert fetched.json() == created

    stored = db_api_client.get(f"/api/v1/scenarios/{created['scenario_id']}").json()
    assert len(stored["results"]) == 125
    assert stored == created


def test_model_artifact_is_unchanged_by_scenario_creation(
    db_api_client, postgis_session
):
    model_json = MODEL_DIR / "model.json"
    parquet = MODEL_DIR / "predictions-2027.parquet"
    before = (_sha256(model_json), _sha256(parquet))
    hashes_before = postgis_session.execute(
        text("SELECT hashes, metrics FROM model_run")
    ).first()

    items = _predictions(db_api_client)
    _create(db_api_client, selected=[p["territory_id"] for p in _eligible(items)[:2]])

    after = (_sha256(model_json), _sha256(parquet))
    hashes_after = postgis_session.execute(
        text("SELECT hashes, metrics FROM model_run")
    ).first()

    assert after == before
    assert hashes_after == hashes_before


def test_transaction_failure_leaves_no_partial_scenario(
    db_api_client, postgis_session, monkeypatch
):
    from participa_geo.db.repository import Repository

    before = postgis_session.scalar(text("SELECT count(*) FROM scenario"))

    def boom(self, scenario_id, results):
        raise RuntimeError("injected result persistence failure")

    monkeypatch.setattr(Repository, "insert_scenario_results", boom)

    items = _predictions(db_api_client)
    body = {
        "model_run_id": items[0]["model_run_id"],
        "target_year": 2027,
        "territory_ids": [_eligible(items)[0]["territory_id"]],
        "reduction_pp": 3.0,
        "assumption_code": "preventive_exploration",
    }
    failing = TestClient(db_api_client.app, raise_server_exceptions=False)
    response = failing.post("/api/v1/scenarios", json=body)

    assert response.status_code == 500
    after = postgis_session.scalar(text("SELECT count(*) FROM scenario"))
    assert after == before

    # The API session must be usable again after the rollback.
    monkeypatch.undo()
    created = _create(db_api_client, selected=[_eligible(items)[1]["territory_id"]])
    assert created["scenario_id"]


def test_get_scenario_returns_persisted_values_not_recalculated(
    db_api_client, postgis_session
):
    items = _predictions(db_api_client)
    created = _create(
        db_api_client, selected=[p["territory_id"] for p in _eligible(items)[:1]]
    )
    target = created["results"][0]["territory_id"]

    postgis_session.execute(
        text(
            """
            UPDATE scenario_result
            SET hypothetical_abstention_pct = 99.25
            WHERE scenario_id = :scenario_id
              AND reference_territory_id = :territory_id
            """
        ),
        {
            "scenario_id": created["scenario_id"],
            "territory_id": target,
        },
    )
    postgis_session.commit()

    fetched = db_api_client.get(f"/api/v1/scenarios/{created['scenario_id']}")
    assert fetched.status_code == 200
    row = next(r for r in fetched.json()["results"] if r["territory_id"] == target)
    assert row["hypothetical_abstention_pct"] == 99.25


def test_gis_layers_filter_by_scenario_uuid_without_overlap(db_config, db_api_client):
    items = _predictions(db_api_client)
    eligible = _eligible(items)
    first = _create(db_api_client, selected=[eligible[0]["territory_id"]], reduction=2.0)
    second = _create(db_api_client, selected=[eligible[1]["territory_id"]], reduction=5.0)
    assert first["scenario_id"] != second["scenario_id"]

    # GeoServer normally serves the demo database; point it at the isolated test
    # database for this assertion and restore the demo datastore afterwards.
    with _geoserver_database(_settings(db_config)):
        response = db_api_client.get(
            "/api/v1/gis/wfs",
            params={
                "request": "GetFeature",
                "typeNames": "scenario_results",
                "scenario_id": first["scenario_id"],
                "srsName": "EPSG:4326",
                "outputFormat": "application/json",
                "count": "125",
            },
        )
        assert response.status_code == 200, response.text
        features = response.json()["features"]
        assert len(features) == 125
        assert {f["properties"]["scenario_id"] for f in features} == {
            first["scenario_id"]
        }

        persisted = {row["municipality_code"]: row for row in first["results"]}
        sample = features[0]["properties"]
        row = persisted[sample["municipality_code"]]
        assert sample["baseline_abstention_pct"] == pytest.approx(
            row["baseline_abstention_pct"]
        )
        assert sample["hypothetical_abstention_pct"] == pytest.approx(
            row["hypothetical_abstention_pct"]
        )

        image = db_api_client.get(
            "/api/v1/gis/wms",
            params={
                "request": "GetMap",
                "layers": "scenario_results",
                "scenario_id": first["scenario_id"],
                "bbox": "-106.0,18.0,-101.0,23.0",
                "width": "256",
                "height": "256",
                "srs": "EPSG:3857",
                "format": "image/png",
            },
        )
        assert image.status_code == 200
        assert image.content.startswith(b"\x89PNG")
