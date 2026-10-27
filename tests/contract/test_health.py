"""Contract tests for the minimal service surface (health and error shape)."""

from __future__ import annotations

import logging


def test_live_is_alive(client_without_dataset):
    response = client_without_dataset.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_ready_without_dataset_is_503(client_without_dataset):
    response = client_without_dataset.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == 503
    assert body["code"] == "not_ready"
    assert body["checks"]["dataset"] is False
    # The remaining prerequisites are also unsatisfied in T1.
    for name in ("database", "migrations", "dataset", "model", "gis"):
        assert body["checks"][name] is False


def test_request_log_contains_the_real_request_id(client_without_dataset, caplog):
    """Item 5: the JSON log is emitted before the contextvar is reset."""
    logger = logging.getLogger("participa_geo.api")
    logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO, logger="participa_geo.api"):
            response = client_without_dataset.get(
                "/api/v1/health/live",
                headers={"x-request-id": "review-request-id"},
            )
    finally:
        logger.removeHandler(caplog.handler)

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "review-request-id"
    records = [
        record
        for record in caplog.records
        if record.getMessage() == "http_request"
    ]
    assert records, "expected an http_request log record"
    assert records[-1].request_id == "review-request-id"
    assert records[-1].path == "/api/v1/health/live"


def test_validation_uses_problem_json(client_with_validation_route):
    response = client_with_validation_route.post(
        "/api/v1/probe",
        json={"value": "not-an-integer"},
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    for field in ("type", "title", "status", "detail", "instance", "code", "request_id"):
        assert field in body, f"missing field {field!r}"
    assert body["status"] == 422
    assert body["code"] == "validation_error"
    assert body["instance"] == "/api/v1/probe"


def test_validation_rejects_extra_fields(client_with_validation_route):
    response = client_with_validation_route.post(
        "/api/v1/probe",
        json={"value": 1, "extra": "nope"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
