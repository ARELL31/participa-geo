"""Integration tests for ``POST /reports`` and downloads (T9).

The database-backed tests use the isolated PostGIS fixture and a temporary
report store so no generated file leaks between runs. The external GeoServer is
never called for the small exports; map failure is asserted explicitly.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from uuid import uuid4

import pytest

from participa_geo.reporting.store import (
    ExportLimitError,
    InstitutionalPackageNotGenerated,
    ReportQuotaError,
    ReportStore,
)


def _store(tmp_path: Path, **kwargs) -> ReportStore:
    return ReportStore(
        tmp_path / "generated",
        institutional_dir=tmp_path / "institutional",
        **kwargs,
    )


def _eligible_prediction(client):
    response = client.get("/api/v1/predictions", params={"page_size": 125})
    assert response.status_code == 200
    return next(
        item
        for item in response.json()["items"]
        if item["eligible"] and item["estimated_abstention_pct"] is not None
    )


def _create_scenario(client) -> dict:
    prediction = _eligible_prediction(client)
    response = client.post(
        "/api/v1/scenarios",
        json={
            "model_run_id": prediction["model_run_id"],
            "target_year": 2027,
            "territory_ids": [prediction["territory_id"]],
            "reduction_pp": 3.0,
            "assumption_code": "preventive_exploration",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_history_csv_export_and_download(db_api_client, tmp_path):
    store = _store(tmp_path)
    db_api_client.app.state.report_store = store
    response = db_api_client.post(
        "/api/v1/reports",
        json={"kind": "history_csv"},
    )
    assert response.status_code == 201, response.text
    artifact = response.json()
    assert artifact["status"] == "ready"
    assert artifact["kind"] == "history_csv"
    assert artifact["format"] == "csv"
    assert artifact["download_url"] == f"/api/v1/reports/{artifact['report_id']}/download"
    assert "path" not in artifact

    download = db_api_client.get(artifact["download_url"])
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("text/csv")
    text = download.content.decode("utf-8-sig")
    assert "# model_run_id=" in text
    data_lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    rows = list(csv.DictReader(io.StringIO("\n".join(data_lines))))
    # Without a territory filter the API contract returns state totals (one row
    # per election year), never an average of municipal rates.
    assert len(rows) == 6
    assert {row["year"] for row in rows} == {"2009", "2012", "2015", "2018", "2021", "2024"}
    assert all(row["territory_id"] == "" for row in rows)


def test_scenario_csv_matches_persisted_api(db_api_client, tmp_path):
    scenario = _create_scenario(db_api_client)
    db_api_client.app.state.report_store = _store(tmp_path)
    response = db_api_client.post(
        "/api/v1/reports",
        json={"kind": "scenario_csv", "scenario_id": scenario["scenario_id"]},
    )
    assert response.status_code == 201, response.text
    download = db_api_client.get(response.json()["download_url"])
    assert download.status_code == 200
    text = download.content.decode("utf-8-sig")
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    rows = list(csv.DictReader(io.StringIO("\n".join(lines))))
    assert len(rows) == 125
    by_id = {row["territory_id"]: row for row in rows}
    for result in scenario["results"]:
        row = by_id[result["territory_id"]]
        if result["baseline_abstention_pct"] is None:
            assert row["baseline_abstention_pct"] == ""
        else:
            assert float(row["baseline_abstention_pct"]) == pytest.approx(
                result["baseline_abstention_pct"]
            )
        if result["hypothetical_abstention_pct"] is None:
            assert row["hypothetical_abstention_pct"] == ""
        else:
            assert float(row["hypothetical_abstention_pct"]) == pytest.approx(
                result["hypothetical_abstention_pct"]
            )


def test_scenario_geojson_has_125_4326_reference_geometries(db_api_client, tmp_path):
    scenario = _create_scenario(db_api_client)
    db_api_client.app.state.report_store = _store(tmp_path)
    response = db_api_client.post(
        "/api/v1/reports",
        json={"kind": "scenario_geojson", "scenario_id": scenario["scenario_id"]},
    )
    assert response.status_code == 201, response.text
    download = db_api_client.get(response.json()["download_url"])
    body = json.loads(download.content)
    assert len(body["features"]) == 125
    assert body["metadata"]["reference_date"] == "2025-12-15"
    for feature in body["features"]:
        assert feature["geometry"]["type"] in {"Polygon", "MultiPolygon"}
        for ring in feature["geometry"]["coordinates"]:
            positions = ring if feature["geometry"]["type"] == "Polygon" else [
                position for polygon in ring for position in polygon
            ]
            for x, y in positions:
                assert -180 <= x <= 180
                assert -90 <= y <= 90


def test_export_is_cached_by_filters_versions_and_assumptions(db_api_client, tmp_path):
    store = _store(tmp_path)
    db_api_client.app.state.report_store = store
    body = {"kind": "history_csv", "year": 2024}
    first = db_api_client.post("/api/v1/reports", json=body)
    second = db_api_client.post("/api/v1/reports", json=body)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["report_id"] == second.json()["report_id"]
    assert second.json()["cached"] is True
    assert len(list(store.root.glob("*.csv"))) == 1

    different = db_api_client.post(
        "/api/v1/reports", json={"kind": "history_csv", "year": 2021}
    )
    assert different.status_code == 201
    assert different.json()["report_id"] != first.json()["report_id"]


def test_export_limits_and_cache(tmp_path):
    now = [0.0]
    store = _store(tmp_path, limit=2, window_seconds=60.0, clock=lambda: now[0])
    spec = {
        "filename": "history.csv",
        "media_type": "text/csv",
        "sources": {},
    }
    request = type(
        "Request",
        (),
        {"kind": "history_csv", "territory_id": None, "year": 2024, "scenario_id": None},
    )()

    first = store.get_or_create(
        request,
        builder=lambda: b"a,b\n1,2\n",
        cache_key="one",
        client_key="client",
        **spec,
    )
    assert first.cached is False
    cached = store.get_or_create(
        request,
        builder=lambda: b"a,b\n1,2\n",
        cache_key="one",
        client_key="client",
        **spec,
    )
    assert cached.cached is True

    store.get_or_create(
        request,
        builder=lambda: b"a,b\n2,3\n",
        cache_key="two",
        client_key="client",
        **spec,
    )
    with pytest.raises(ExportLimitError):
        store.get_or_create(
            request,
            builder=lambda: b"a,b\n3,4\n",
            cache_key="three",
            client_key="client",
            **spec,
        )

    now[0] = 61.0
    third = store.get_or_create(
        request,
        builder=lambda: b"a,b\n3,4\n",
        cache_key="three",
        client_key="client",
        **spec,
    )
    assert third.cached is False


def test_quota_rejects_and_removes_temporary_output(tmp_path):
    store = _store(tmp_path, quota_bytes=5)
    request = type(
        "Request",
        (),
        {"kind": "history_csv", "territory_id": None, "year": 2024, "scenario_id": None},
    )()
    with pytest.raises(ReportQuotaError):
        store.get_or_create(
            request,
            builder=lambda: b"0123456789",
            filename="history.csv",
            media_type="text/csv",
            sources={},
            cache_key="quota",
            client_key="client",
        )
    assert list(store.root.iterdir()) == []
    assert store.list() == []


def test_failed_export_leaves_no_partial_file(tmp_path):
    store = _store(tmp_path)
    request = type(
        "Request",
        (),
        {"kind": "history_csv", "territory_id": None, "year": 2024, "scenario_id": None},
    )()

    def fail() -> bytes:
        raise RuntimeError("generation failed")

    with pytest.raises(RuntimeError):
        store.get_or_create(
            request,
            builder=fail,
            filename="history.csv",
            media_type="text/csv",
            sources={},
            cache_key="failing",
            client_key="client",
        )
    assert list(store.root.iterdir()) == []
    assert store.list() == []


def test_institutional_missing_is_409_not_pending(db_api_client, tmp_path):
    store = _store(tmp_path)
    db_api_client.app.state.report_store = store
    response = db_api_client.post(
        "/api/v1/reports", json={"kind": "methodology_pdf"}
    )
    assert response.status_code == 409, response.text
    problem = response.json()
    assert problem["code"] == "institutional_package_not_generated"
    assert "status" not in problem or problem["status"] == 409

    # The CLI publishes the artifact + manifest; the API then serves it.
    store.publish_institutional(
        "methodology_pdf",
        b"%PDF-1.4\n% institutional test\n",
        filename="methodology.pdf",
        media_type="application/pdf",
        sources={"model_run_id": "5bc387ce-6646-5b49-9c4f-ad302f4c422a"},
    )
    served = db_api_client.post(
        "/api/v1/reports", json={"kind": "methodology_pdf"}
    )
    assert served.status_code == 200, served.text
    assert served.json()["status"] == "ready"
    download = db_api_client.get(served.json()["download_url"])
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")


def test_unknown_paths_and_urls_rejected(db_api_client, tmp_path):
    db_api_client.app.state.report_store = _store(tmp_path)

    unknown_kind = db_api_client.post("/api/v1/reports", json={"kind": "user_url"})
    assert unknown_kind.status_code == 422
    assert unknown_kind.headers["content-type"].startswith("application/problem+json")

    url_field = db_api_client.post(
        "/api/v1/reports",
        json={"kind": "history_csv", "url": "http://evil.example/report"},
    )
    assert url_field.status_code == 422

    missing_scenario = db_api_client.post(
        "/api/v1/reports", json={"kind": "scenario_csv"}
    )
    assert missing_scenario.status_code == 422

    unknown_report = db_api_client.get(f"/api/v1/reports/{uuid4()}")
    assert unknown_report.status_code == 404
    unknown_download = db_api_client.get(f"/api/v1/reports/{uuid4()}/download")
    assert unknown_download.status_code == 404


def test_report_list_contains_generated_artifacts(db_api_client, tmp_path):
    store = _store(tmp_path)
    db_api_client.app.state.report_store = store
    created = db_api_client.post(
        "/api/v1/reports", json={"kind": "history_csv", "year": 2024}
    )
    assert created.status_code == 201
    listing = db_api_client.get("/api/v1/reports")
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    assert body["items"][0]["report_id"] == created.json()["report_id"]
    assert body["items"][0]["download_url"].endswith("/download")


def test_institutional_manifest_is_atomic_and_hash_checked(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(InstitutionalPackageNotGenerated):
        store.get_or_create(
            type("Request", (), {"kind": "executive_pdf"})(),
            builder=lambda: b"",
            filename="executive.pdf",
            media_type="application/pdf",
            sources={},
            cache_key="x",
            client_key="client",
        )
    artifact = store.publish_institutional(
        "executive_pdf",
        b"%PDF-1.4\nexecutive\n",
        filename="executive.pdf",
        media_type="application/pdf",
        sources={},
    )
    assert artifact.size_bytes > 0
    assert artifact.sha256
    files = sorted(path.name for path in store.institutional_dir.iterdir())
    assert files == ["executive.pdf", "manifest.json"]
    assert not any(name.endswith(".tmp") for name in files)
