"""End-to-end GeoServer tests: WMS/WFS are published and read-only.

These hit the real GeoServer over the internal network (``GIS_BASE_URL``). They
require ``gis publish`` to have run (the layers exist). They assert a real
EPSG:3857 WMS GetMap PNG, a real EPSG:4326 WFS GetFeature with 125 features, and
that a WFS ``Transaction`` is rejected (WFS-T disabled).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from pyproj import Transformer

GIS_BASE_URL = os.environ.get("GIS_BASE_URL", "http://geoserver:8080/geoserver")

LAYER = "participa_geo:municipalities"


def _get(url: str, timeout: float = 60.0):
    request = urllib.request.Request(url)
    request.add_header("Accept", "*/*")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.headers.get_content_type(), response.read()


def _post(url: str, body: bytes, content_type: str):
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(request, timeout=60.0) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def test_wms_getcapabilities_lists_municipalities():
    status, _, body = _get(
        f"{GIS_BASE_URL}/wms?service=WMS&version=1.3.0&request=GetCapabilities"
    )
    assert status == 200
    assert b"municipalities" in body


def test_wms_and_wfs_read_only():
    # --- WMS GetMap (EPSG:3857) must return a non-empty PNG -----------------
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x1, y1 = transformer.transform(-105.7, 18.9)
    x2, y2 = transformer.transform(-101.5, 22.75)
    bbox = f"{x1},{y1},{x2},{y2}"

    status, content_type, png = _get(
        f"{GIS_BASE_URL}/wms?service=WMS&version=1.1.1&request=GetMap"
        f"&layers={LAYER}&styles="
        f"&bbox={bbox}&width=512&height=512&srs=EPSG:3857&format=image/png"
    )
    assert status == 200
    assert content_type == "image/png"
    assert len(png) > 0
    assert png.startswith(b"\x89PNG")

    # --- WFS GetFeature (EPSG:4326) must return 125 features -----------------
    status, content_type, geojson = _get(
        f"{GIS_BASE_URL}/wfs?service=WFS&version=2.0.0&request=GetFeature"
        f"&typeNames={LAYER}&srsName=EPSG:4326&outputFormat=application/json"
    )
    assert status == 200
    payload = json.loads(geojson.decode("utf-8"))
    features = payload.get("features", [])
    assert len(features) == 125


def test_wfs_transaction_rejected():
    transaction = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<wfs:Transaction service="WFS" version="2.0.0" '
        'xmlns:wfs="http://www.opengis.net/wfs/2.0">'
        f'<wfs:Delete typeName="{LAYER}">'
        '<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0">'
        "<fes:ResourceId rid=\"anything\"/>"
        "</fes:Filter>"
        "</wfs:Delete>"
        "</wfs:Transaction>"
    )
    _, body = _post(
        f"{GIS_BASE_URL}/wfs?service=WFS&version=2.0.0&request=Transaction",
        transaction.encode("utf-8"),
        "application/xml",
    )
    # With WFS-T disabled a successful TransactionResponse must never appear.
    assert b"TransactionResponse" not in body
    assert b"transaction" in body.lower() or b"operation" in body.lower()
