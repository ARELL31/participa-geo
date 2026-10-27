"""Contract tests for ``POST /scenarios``, ``GET /scenarios/{id}`` and
``GET /recommendations`` (T6).

They run against the isolated PostGIS test database and the real published model
loaded by T5. Validation-only cases use the database-free client.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = REPO_ROOT / "docs" / "api" / "openapi.json"

REQUEST_KEYS = {
    "model_run_id",
    "target_year",
    "territory_ids",
    "reduction_pp",
    "assumption_code",
}


def _predictions(client) -> dict:
    response = client.get("/api/v1/predictions", params={"page_size": 125})
    assert response.status_code == 200
    return response.json()


def _eligible(payload: dict) -> list[dict]:
    return [
        p
        for p in payload["items"]
        if p["eligible"] and p["estimated_abstention_pct"] is not None
    ]


def _insufficient(payload: dict) -> list[dict]:
    return [p for p in payload["items"] if not p["eligible"]]


def _valid_body(client, *, territory_ids=None, reduction=3.0) -> dict:
    payload = _predictions(client)
    ids = territory_ids or [_eligible(payload)[0]["territory_id"]]
    return {
        "model_run_id": payload["meta"]["model_run_id"],
        "target_year": 2027,
        "territory_ids": ids,
        "reduction_pp": reduction,
        "assumption_code": "preventive_exploration",
    }


def _post(client, body):
    return client.post("/api/v1/scenarios", json=body)


def test_create_returns_full_persisted_comparison(db_api_client, loaded_model_run_id):
    payload = _predictions(db_api_client)
    eligible = _eligible(payload)
    selected = eligible[:2]
    body = _valid_body(
        db_api_client,
        territory_ids=[item["territory_id"] for item in selected],
        reduction=3.0,
    )

    response = _post(db_api_client, body)

    assert response.status_code == 201
    scenario = response.json()
    assert scenario["scenario_id"]
    assert scenario["model_run_id"] == str(loaded_model_run_id)
    assert scenario["target_year"] == 2027
    assert scenario["requested_reduction_pp"] == 3.0
    assert scenario["assumption_code"] == "preventive_exploration"
    assert scenario["assumption_version"]
    assert scenario["rules_version"]
    assert scenario["rationale_text"]
    assert len(scenario["input_sha256"]) == 64
    assert len(scenario["model_sha256"]) == 64
    assert set(scenario["selected_territory_ids"]) == {
        item["territory_id"] for item in selected
    }
    assert "histórico" in scenario["error_band_label"].lower()
    assert "causal" in scenario["error_band_label"].lower()

    # Exactly the 125-municipality universe is persisted, including nulls.
    assert len(scenario["results"]) == 125
    by_id = {row["territory_id"]: row for row in scenario["results"]}

    for prediction in selected:
        row = by_id[prediction["territory_id"]]
        assert row["selected"] is True
        expected_b = max(0.0, prediction["estimated_abstention_pct"] - 3.0)
        expected_effective = prediction["estimated_abstention_pct"] - expected_b
        assert row["baseline_abstention_pct"] == pytest.approx(
            prediction["estimated_abstention_pct"]
        )
        assert row["hypothetical_abstention_pct"] == pytest.approx(expected_b)
        assert row["effective_reduction_pp"] == pytest.approx(expected_effective)
        assert row["requested_reduction_pp"] == 3.0
        assert row["risk_a"] == prediction["risk"]

    unselected = next(
        p
        for p in eligible
        if not by_id[p["territory_id"]]["selected"]
    )
    row = by_id[unselected["territory_id"]]
    assert row["hypothetical_abstention_pct"] == row["baseline_abstention_pct"]
    assert row["effective_reduction_pp"] == 0.0

    for prediction in _insufficient(payload):
        row = by_id[prediction["territory_id"]]
        assert row["baseline_abstention_pct"] is None
        assert row["hypothetical_abstention_pct"] is None
        assert row["risk_a"] == "insufficient"
        assert row["risk_b"] == "insufficient"

    # GET is byte-for-byte the persisted comparison (no recalculation).
    fetched = db_api_client.get(f"/api/v1/scenarios/{scenario['scenario_id']}")
    assert fetched.status_code == 200
    assert fetched.json() == scenario


def test_unknown_scenario_is_404_problem(db_api_client):
    response = db_api_client.get(f"/api/v1/scenarios/{uuid4()}")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "not_found"
    assert body["status"] == 404
    for field in ("type", "title", "detail", "instance", "request_id"):
        assert field in body


def test_insufficient_selected_is_422_with_identifier_and_cause(db_api_client):
    payload = _predictions(db_api_client)
    insufficient = _insufficient(payload)[0]
    body = _valid_body(
        db_api_client, territory_ids=[insufficient["territory_id"]]
    )

    response = _post(db_api_client, body)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["code"] == "validation_error"
    assert problem["errors"]
    error = problem["errors"][0]
    assert error["territory_id"] == insufficient["territory_id"]
    assert error["reason"]


def test_unknown_territory_and_model_are_422(db_api_client):
    unknown_body = _valid_body(
        db_api_client, territory_ids=[str(uuid4())]
    )
    response = _post(db_api_client, unknown_body)
    assert response.status_code == 422
    assert response.json()["errors"][0]["reason"]

    bad_model = _valid_body(db_api_client)
    bad_model["model_run_id"] = str(uuid4())
    response = _post(db_api_client, bad_model)
    assert response.status_code == 422
    assert response.json()["errors"][0]["reason"]


def test_duplicate_nan_extra_fields_and_bad_rationale_are_rejected(api_client):
    base = {
        "model_run_id": str(uuid4()),
        "target_year": 2027,
        "territory_ids": [str(uuid4())],
        "reduction_pp": 3.0,
        "assumption_code": "preventive_exploration",
    }

    duplicate = dict(base, territory_ids=[base["territory_ids"][0]] * 2)
    assert _post(api_client, duplicate).status_code == 422

    empty = dict(base, territory_ids=[])
    assert _post(api_client, empty).status_code == 422

    too_many = dict(base, territory_ids=[str(uuid4()) for _ in range(126)])
    assert _post(api_client, too_many).status_code == 422

    extra = dict(base, rationale_text="texto libre no permitido")
    assert _post(api_client, extra).status_code == 422

    for reduction in (-0.1, 10.1):
        assert _post(api_client, dict(base, reduction_pp=reduction)).status_code == 422

    for field, value in (
        ("assumption_code", "porque_conviene"),
        ("target_year", 2026),
    ):
        assert _post(api_client, dict(base, **{field: value})).status_code == 422

    for non_finite in (float("nan"), float("inf"), float("-inf")):
        raw = json.dumps(dict(base, reduction_pp=non_finite))
        response = api_client.post(
            "/api/v1/scenarios",
            content=raw,
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422, non_finite


def test_eleventh_creation_in_a_minute_is_429(db_api_client):
    body = _valid_body(db_api_client)
    for _ in range(10):
        assert _post(db_api_client, body).status_code == 201

    response = _post(db_api_client, body)

    assert response.status_code == 429
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["status"] == 429
    assert problem["code"] == "rate_limited"
    assert problem["request_id"]


def test_recommendations_are_versioned_and_neutral(db_api_client):
    payload = _predictions(db_api_client)
    response = db_api_client.get("/api/v1/recommendations", params={"page_size": 125})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 125
    assert len(body["items"]) == 125
    assert body["meta"]["model_run_id"] == payload["meta"]["model_run_id"]

    first = body["items"][0]
    assert first["rules_version"]
    assert first["recommendations"]
    for recommendation in first["recommendations"]:
        assert recommendation["version"]
        assert recommendation["reasons"]
        assert recommendation["title"]
        assert recommendation["action"]

    text = json.dumps(body, ensure_ascii=False).lower()
    for forbidden in ("presupuesto", "partido", "movilizar", "segmentación persuasiva"):
        assert forbidden not in text

    with_reasons = next(
        p
        for p in payload["items"]
        if (p.get("quality") or {}).get("reasons")
    )
    single = db_api_client.get(
        "/api/v1/recommendations",
        params={"territory_id": with_reasons["territory_id"]},
    )
    assert single.status_code == 200
    item = single.json()["items"][0]
    codes = {r["code"] for r in item["recommendations"]}
    if "high_unknown_share" in (with_reasons.get("quality") or {}).get("reasons", []):
        assert "improve_data_quality" in codes


def test_openapi_declares_scenario_contract():
    openapi = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    for path in (
        "/api/v1/scenarios",
        "/api/v1/scenarios/{scenario_id}",
        "/api/v1/recommendations",
    ):
        assert path in openapi["paths"], path

    post = openapi["paths"]["/api/v1/scenarios"]["post"]
    assert "201" in post["responses"]

    schema_ref = post["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema_name = schema_ref.rsplit("/", 1)[-1]
    schema = openapi["components"]["schemas"][schema_name]

    assert set(schema["properties"]) == REQUEST_KEYS
    assert schema.get("additionalProperties") is False
    assert set(schema["required"]) == REQUEST_KEYS

    target = schema["properties"]["target_year"]
    assert target.get("const") == 2027 or target.get("enum") == [2027]

    reduction = schema["properties"]["reduction_pp"]
    assert reduction["minimum"] == 0.0
    assert reduction["maximum"] == 10.0

    territories = schema["properties"]["territory_ids"]
    assert territories["minItems"] == 1
    assert territories["maxItems"] == 125

    assumption = schema["properties"]["assumption_code"]
    assert set(assumption["enum"]) == {"preventive_exploration", "model_sensitivity"}

    create_response = post["responses"]["201"]["content"]["application/json"]["schema"]
    assert create_response
