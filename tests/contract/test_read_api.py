"""Contract tests for the read API (``/api/v1``).

These run against the migrated and loaded test database (see ``tests/conftest.py``)
and pin the HTTP contract: stable pagination, summed state history, null/``insufficient``
predictions, validation errors and 404s in ``application/problem+json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = REPO_ROOT / "docs" / "api" / "openapi.json"

#: State totals from docs/methodology/evidence/jalisco-audit.json (2009).
EVIDENCE_2009 = {"ln": 5133870, "sv": 2570273, "nv": 2450936, "ns": 112661}
EVIDENCE_2009_ABSTENTION_PCT = 48.811670655413864


def test_territories_are_stably_paginated(db_api_client):
    response = db_api_client.get("/api/v1/territories")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["total"] == 125
    assert body["page_size"] == 25
    assert body["page"] == 1
    assert len(body["items"]) == 25
    codes = [t["municipality_code"] for t in body["items"]]
    # Stable numeric order by zero-padded INE municipality code.
    assert codes == [f"{i:03d}" for i in range(1, 26)]
    # The envelope carries the versioned metadata.
    assert body["meta"]["reference_date"] == "2025-12-15"
    assert isinstance(body["meta"]["dataset_version_ids"], list)


def test_history_state_uses_summed_counts(db_api_client):
    response = db_api_client.get("/api/v1/participation/history", params={"page_size": 125})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 6
    by_year = {r["year"]: r for r in body["items"]}

    # State aggregates sum the 125 municipalities before computing rates.
    row = by_year[2009]
    assert row["territory_id"] is None
    assert row["ln"] == EVIDENCE_2009["ln"]
    assert row["sv"] == EVIDENCE_2009["sv"]
    assert row["nv"] == EVIDENCE_2009["nv"]
    assert row["ns"] == EVIDENCE_2009["ns"]
    assert abs(row["abstention_pct"] - EVIDENCE_2009_ABSTENTION_PCT) < 1e-6
    assert abs(row["participation_pct"] - (100 - EVIDENCE_2009_ABSTENTION_PCT)) < 1e-6


def test_insufficient_prediction_is_null(db_api_client):
    response = db_api_client.get("/api/v1/predictions", params={"page_size": 125})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 125
    insufficient = [p for p in body["items"] if p["risk"] == "insufficient"]
    assert insufficient, "expected some insufficient predictions"
    for p in insufficient:
        assert p["estimated_abstention_pct"] is None
        assert p["historical_error_lower_pct"] is None
        assert p["historical_error_upper_pct"] is None
        assert p["eligible"] is False
        assert p["risk"] == "insufficient"


def test_state_history_honours_page_and_page_size(db_api_client):
    first = db_api_client.get("/api/v1/participation/history", params={"page": 1, "page_size": 1})
    assert first.status_code == 200
    body = first.json()
    assert body["total"] == 6
    assert body["page"] == 1 and body["page_size"] == 1
    assert [row["year"] for row in body["items"]] == [2009]

    second = db_api_client.get("/api/v1/participation/history", params={"page": 2, "page_size": 1})
    assert second.status_code == 200
    body = second.json()
    assert body["total"] == 6
    assert [row["year"] for row in body["items"]] == [2012]


def test_invalid_year_and_page_rejected(db_api_client):
    # year=2023 is not a CCPC election year.
    response = db_api_client.get("/api/v1/participation/history", params={"year": 2023})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"

    # page must be >= 1.
    response = db_api_client.get("/api/v1/territories", params={"page": 0})
    assert response.status_code == 422

    # page_size is bounded at 500.
    response = db_api_client.get("/api/v1/territories", params={"page_size": 501})
    assert response.status_code == 422


@pytest.mark.parametrize("year", [2009, 2012, 2015, 2018, 2021, 2024])
def test_history_year_filter_accepts_all_years(db_api_client, year):
    # Regression: query-string `year` values must coerce to int and pass the
    # Literal check (Pydantic 2.14 rejected `"2024"` with `literal_error`).
    response = db_api_client.get("/api/v1/participation/history", params={"year": year})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["year"] == year


def test_history_year_invalid_is_422_problem_json(db_api_client):
    response = db_api_client.get("/api/v1/participation/history", params={"year": 2023})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"


def test_unknown_id_404(db_api_client):
    response = db_api_client.get("/api/v1/models/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "not_found"


def test_models_list_and_get(db_api_client, loaded_model_run_id):
    response = db_api_client.get("/api/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["model_run_id"] == str(loaded_model_run_id)
    assert body["items"][0]["family"] == "M0"
    assert body["items"][0]["target_year"] == 2027

    single = db_api_client.get(f"/api/v1/models/{loaded_model_run_id}")
    assert single.status_code == 200
    assert single.json()["model_run_id"] == str(loaded_model_run_id)


def test_old_municipal_model_is_not_api_accessible(
    db_api_client, postgis_session, loaded_model_run_id
):
    from participa_geo.db.models import ModelRun

    old_model_id = uuid4()
    postgis_session.add(ModelRun(id=old_model_id, family="legacy-jalisco"))
    postgis_session.commit()

    listed = db_api_client.get("/api/v1/models", params={"level": "municipality"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["model_run_id"] == str(loaded_model_run_id)

    detail = db_api_client.get(f"/api/v1/models/{old_model_id}")
    assert detail.status_code == 404
    assert detail.json()["code"] == "not_found"

    predictions = db_api_client.get(
        "/api/v1/predictions", params={"model_run_id": str(old_model_id)}
    )
    assert predictions.status_code == 404
    assert predictions.json()["code"] == "not_found"


def test_district_models_are_unavailable(api_client):
    response = api_client.get("/api/v1/models", params={"level": "federal_district"})
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "district_model_unavailable"


def test_predictions_default_to_published_model(db_api_client, loaded_model_run_id):
    response = db_api_client.get("/api/v1/predictions", params={"page_size": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 125
    assert body["items"][0]["model_run_id"] == str(loaded_model_run_id)
    assert body["meta"]["model_run_id"] == str(loaded_model_run_id)


def test_predictions_target_year_2027_accepted(db_api_client):
    # Regression: the query-string `target_year` must coerce to int and pass the
    # Literal check (Pydantic 2.14 rejected `"2027"` with `literal_error`).
    response = db_api_client.get(
        "/api/v1/predictions", params={"target_year": 2027, "page_size": 1}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 125
    assert body["items"][0]["target_year"] == 2027


def test_predictions_target_year_2026_rejected(db_api_client):
    response = db_api_client.get("/api/v1/predictions", params={"target_year": 2026})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"


def test_federal_district_predictions_fail_with_stable_409(api_client):
    response = api_client.get("/api/v1/predictions", params={"level": "federal_district"})
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "district_model_unavailable"


def _query_params(openapi: dict, path: str) -> dict[str, dict]:
    return {
        p["name"]: p
        for p in openapi["paths"][path]["get"].get("parameters", [])
        if p.get("in") == "query"
    }


def test_openapi_matches_contract():
    openapi = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))

    # Every read route lives under the fixed prefix.
    for path in (
        "/api/v1/territories",
        "/api/v1/participation/history",
        "/api/v1/participation/summary",
        "/api/v1/models",
        "/api/v1/predictions",
        "/api/v1/gis/wms",
        "/api/v1/gis/wfs",
    ):
        assert path in openapi["paths"], path

    # Pagination bounds: page >= 1, page_size 1..500 default 25.
    territories = _query_params(openapi, "/api/v1/territories")
    assert territories["page"]["schema"]["minimum"] == 1
    assert territories["page_size"]["schema"]["minimum"] == 1
    assert territories["page_size"]["schema"]["maximum"] == 500
    assert territories["page_size"]["schema"]["default"] == 25
    assert territories["state_code"]["schema"]["default"] == "14"

    # Historical year enum is exactly the six CCPC election years.
    history = _query_params(openapi, "/api/v1/participation/history")
    year_schema = history["year"]["schema"]
    year_enum = year_schema.get("enum")
    if year_enum is None:
        year_enum = next(opt["enum"] for opt in year_schema.get("anyOf", []) if "enum" in opt)
    assert year_enum == [2009, 2012, 2015, 2018, 2021, 2024]

    # Predictions default to the 2027 horizon.
    predictions = _query_params(openapi, "/api/v1/predictions")
    assert predictions["target_year"]["schema"]["default"] == 2027
    assert predictions["page_size"]["schema"]["maximum"] == 500
    assert "level" in predictions
    assert "state_code" in predictions
    assert "level" in _query_params(openapi, "/api/v1/models")
    assert "level" in _query_params(openapi, "/api/v1/recommendations")
    assert "level" in _query_params(openapi, "/api/v1/participation/summary")
