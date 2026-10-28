"""National response-time and volume gates against the live API/GIS stack."""

from __future__ import annotations

import json
import os
import time
from urllib.request import urlopen

import pytest

BASE_URL = os.environ.get("NATIONAL_ACCEPTANCE_API", "http://127.0.0.1:8000")
WMS = (
    "/api/v1/gis/wms?service=WMS&version=1.1.1&request=GetMap"
    "&layers=participa_geo_national:states&styles="
    "&bbox=-13884900,2870000,-7450000,6230000&width=1200&height=900"
    "&srs=EPSG:3857&format=image/png"
)
WFS = (
    "/api/v1/gis/wfs?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=participa_geo_national:municipalities&state_code=14"
    "&count=1000&outputFormat=application/json"
)
PAGE_500 = (
    "/api/v1/territories?level=municipality&state_code=14&page=1&page_size=500"
)
SUMMARY_32 = "/api/v1/participation/summary?level=municipality&year=2024"


def _get(path: str) -> tuple[float, str, bytes]:
    started = time.perf_counter()
    with urlopen(f"{BASE_URL}{path}", timeout=10) as response:
        body = response.read()
        content_type = response.headers.get("content-type", "")
    return time.perf_counter() - started, content_type, body


def _warm_p95(path: str, sample_count: int = 30) -> float:
    samples = [_get(path)[0] for _ in range(sample_count)]
    return sorted(samples)[int(0.95 * (sample_count - 1))]


def test_national_wms_cold_and_warm_latency() -> None:
    cold, content_type, body = _get(WMS)
    assert content_type.startswith("image/png")
    assert body.startswith(b"\x89PNG\r\n\x1a\n")
    assert cold <= 5.0
    assert _warm_p95(WMS, sample_count=10) <= 2.5


def test_state_wfs_is_bounded_and_under_three_seconds() -> None:
    elapsed, content_type, body = _get(WFS)
    assert elapsed <= 3.0
    assert "json" in content_type
    collection = json.loads(body)
    assert len(collection["features"]) <= 1000


@pytest.mark.parametrize("path", [PAGE_500, SUMMARY_32])
def test_national_api_warm_latency(path: str) -> None:
    elapsed, _, body = _get(path)
    assert json.loads(body)
    limit = 0.5 if path == PAGE_500 else 1.0
    assert _warm_p95(path) <= limit
