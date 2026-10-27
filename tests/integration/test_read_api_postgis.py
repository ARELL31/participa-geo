"""Integration tests for the read API over PostGIS and the GIS gateway.

These exercise the HTTP layer against the isolated test database plus the real
GeoServer (``GIS_BASE_URL``): readiness, read-only behaviour, malicious ``q``
escaping, model-load idempotency, and the bounded GIS gateway proxy.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = REPO_ROOT / "data" / "processed" / "model"


def _readiness_client(readiness: dict[str, bool]) -> TestClient:
    from participa_geo.main import create_app
    from participa_geo.settings import Settings

    app = create_app(
        Settings(
            _env_file=None,
            db_api_password="test-api-password",
            gis_admin_password="test-gis-password",
        ),
        readiness=lambda: readiness,
    )
    return TestClient(app)


def test_ready_200_when_all_available(db_api_client):
    response = db_api_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    for name in ("database", "migrations", "dataset", "model", "gis"):
        assert body["checks"][name] is True


def test_ready_503_when_model_missing():
    client = _readiness_client(
        {"database": True, "migrations": True, "dataset": True, "model": False, "gis": True}
    )
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "not_ready"
    assert body["checks"]["model"] is False
    assert body["checks"]["gis"] is True


def test_ready_503_when_gis_unavailable():
    client = _readiness_client(
        {"database": True, "migrations": True, "dataset": True, "model": True, "gis": False}
    )
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "not_ready"
    assert body["checks"]["gis"] is False


def test_malicious_q_is_escaped(db_api_client):
    for q in ("%", "_", "!", "'; DROP TABLE observation;--", "OR 1=1"):
        response = db_api_client.get("/api/v1/territories", params={"q": q})
        assert response.status_code == 200
        assert response.json()["total"] == 0, q
    # No SQL injection and no secret/trace leaks into the response. (The query
    # string is echoed verbatim in ``meta.filters`` — the caller's own input —
    # but is never interpolated into SQL, and no credential is ever emitted.)
    response = db_api_client.get(
        "/api/v1/territories", params={"q": "'; DROP TABLE observation;--"}
    )
    assert response.status_code == 200
    text_body = response.text.lower()
    assert "password" not in text_body
    assert "db_api_password" not in text_body
    assert "traceback" not in text_body


def test_prediction_values_match_artifact(db_api_client):
    response = db_api_client.get("/api/v1/predictions", params={"page_size": 125})
    body = response.json()
    by_code = {p["municipality_code"]: p for p in body["items"]}
    # model.json pre_clip_outputs_2027 -> municipality "002" == 45.11343804537522
    # (clipped_count_2027 == 0, so pre-clip equals the served estimate).
    assert by_code["002"]["estimated_abstention_pct"] == pytest.approx(45.11343804537522)
    assert by_code["002"]["risk"] == "medium"


def test_model_load_is_idempotent(db_config, postgis_session):
    from participa_geo.db.repository import load_model_bundle
    from participa_geo.db.session import writer_engine
    from participa_geo.settings import Settings

    settings = Settings(
        _env_file=None,
        db_host=db_config["host"],
        db_port=db_config["port"],
        db_name=db_config["db_name"],
        db_writer_user=db_config["writer_user"],
        db_writer_password=db_config["writer_password"],
        db_api_user=db_config["api_user"],
        db_api_password=db_config["api_password"],
        gis_admin_user=db_config["gis_admin_user"],
        gis_admin_password=db_config["gis_admin_password"],
    )

    first = second = None
    engine = writer_engine(settings)
    with Session(engine) as session:
        first = load_model_bundle(MODEL_DIR, session)
        session.commit()
    with Session(engine) as session:
        second = load_model_bundle(MODEL_DIR, session)
        session.commit()

    assert first == second
    with Session(engine) as session:
        model_count = session.scalar(
            text("SELECT count(*) FROM model_run WHERE id = :id"), {"id": first}
        )
        prediction_count = session.scalar(
            text("SELECT count(*) FROM prediction WHERE model_run_id = :id"), {"id": first}
        )
    engine.dispose()
    assert model_count == 1
    assert prediction_count == 125


def test_gis_gateway_wms_getmap_via_proxy(db_api_client):
    response = db_api_client.get(
        "/api/v1/gis/wms",
        params={
            "request": "GetMap",
            "layers": "municipalities",
            "bbox": "-106.0,18.0,-101.0,23.0",
            "width": "256",
            "height": "256",
            "srs": "EPSG:3857",
            "format": "image/png",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_gis_gateway_wfs_getfeature_via_proxy(db_api_client):
    response = db_api_client.get(
        "/api/v1/gis/wfs",
        params={
            "request": "GetFeature",
            "typeNames": "municipalities",
            "srsName": "EPSG:4326",
            "outputFormat": "application/json",
            "count": "125",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload.get("features", [])) == 125
